#!/usr/bin/env python3
# Prompt-time recall: Claude Code UserPromptSubmit hook. Reads the hook JSON on
# stdin, ranks the memory files against the prompt with BM25 and injects the
# top few *descriptions* (never bodies) as additionalContext, so a memory gets
# recalled even when nobody thought to search for it.
#
# Any failure prints nothing and exits 0: recall must never block a prompt.
# No numpy, no embed backend: it runs on every prompt.
import os, re, sys, json, math, time
from collections import Counter
from mem_common import MEMORY_DIR, LINK_RE, memory_files, parse_file, is_active, tokens

TOP = 3
MIN_WORDS = 4
# raw BM25, name counted twice. Calibrated 2026-11 on a real brain (~470
# files): chit-chat tops out near 8.3, real topic hits score 10 and up. A much
# smaller brain scores lower across the board: lower it there.
FLOOR = 10.0
MIN_TERMS = 2               # distinct query words a hit must share...
RARE_DF = 3                 # ...unless the one it shares is this rare (a name, like a pet's)
K1, B = 1.5, 0.75
CACHE_VERSION = 2
# common words carry no topic; BM25's idf alone still lets them add up on long prompts
STOP = set("""a about after again all also am an and any are as at be been before being but by can
could did do does doing don done for from get got had has have having he her here him his how i if
in into is it its just know let like me more my need no not now of off on one only or our out over
please really right said say see she should so some still such than that the their them then there
these they thing think this those to too up us use very want was we well were what when where which
while who why will with would yeah yes yet you your ok okay hey good great thanks""".split())


# One entry per memory file, rebuilt only for files whose mtime or size moved:
# parsing ~500 files costs 300ms+, a stat sweep a few. Keyed by file stem, the
# one unique id: names repeat, hold spaces, and [[links]] use stems.
def load_corpus(memdir, cache_path):
    try:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("v") != CACHE_VERSION:
            cache = {}
    except (OSError, ValueError):
        cache = {}
    old = cache.get("files", {})
    files, dirty = {}, False
    for path in memory_files(memdir):
        try:
            st = os.stat(path)
        except OSError:
            continue
        key = [st.st_mtime_ns, st.st_size]
        e = old.get(path)
        if not e or e["key"] != key:
            # one unreadable or odd file must not take recall down for every prompt
            try:
                rec = parse_file(path)
                name = str(rec["name"] or "")
                toks = tokens(f"{name} {name} {rec['description'] or ''} {rec['body']}")
                e = {"key": key, "type": str(rec["type"] or ""), "desc": str(rec["description"] or ""),
                     "active": is_active(rec), "len": len(toks), "tf": dict(Counter(toks))}
            except Exception:
                e = {"key": key, "type": "", "desc": "", "active": False, "len": 0, "tf": {}}
            dirty = True
        files[path] = e
    if dirty or len(files) != len(old):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        tmp = f"{cache_path}.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"v": CACHE_VERSION, "files": files}, f)
        os.replace(tmp, cache_path)
    return files


def rank(prompt, files, skip=(), top=TOP, floor=FLOOR):
    q = {w for w in tokens(prompt) if w not in STOP and len(w) > 1}
    if not q or not files:
        return []
    n = len(files)
    avg = sum(e["len"] for e in files.values()) / n or 1
    df = Counter(w for e in files.values() for w in q if w in e["tf"])
    hits = []
    for path, e in files.items():
        stem = os.path.basename(path)[:-3]
        if not e["active"] or stem in skip:
            continue
        tf = e["tf"]
        shared = [w for w in q if w in tf]
        if len(shared) < MIN_TERMS and not (shared and df[shared[0]] <= RARE_DF):
            continue
        sc = 0.0
        for w in shared:
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            sc += idf * tf[w] * (K1 + 1) / (tf[w] + K1 * (1 - B + B * e["len"] / avg))
        if sc >= floor:
            hits.append((sc, stem, e["type"], e["desc"], path))
    hits.sort(key=lambda h: h[0], reverse=True)
    return hits[:top]


# stems CORE already links: their pointer line is in context every session
def core_names(memdir):
    try:
        with open(os.path.join(memdir, "MEMORY.md"), encoding="utf-8") as f:
            return set(LINK_RE.findall(f.read()))
    except OSError:
        return set()


# once a memory has been offered in a session, offering it again is noise
def _seen_path(state_dir, session):
    return os.path.join(state_dir, re.sub(r"[^A-Za-z0-9_-]", "_", session)[:80] or "none")


def load_seen(state_dir, session):
    try:
        with open(_seen_path(state_dir, session), encoding="utf-8") as f:
            return set(f.read().splitlines())
    except OSError:
        return set()


def save_seen(state_dir, session, stems):
    os.makedirs(state_dir, exist_ok=True)
    path = _seen_path(state_dir, session)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(n + "\n" for n in stems))
    if not new:
        return
    # sessions don't say when they end: on a session's first hit, drop files
    # untouched for two days. Best-effort: another session may sweep at once.
    cutoff = time.time() - 2 * 86400
    for e in os.scandir(state_dir):
        try:
            if e.is_file() and e.stat().st_mtime < cutoff:
                os.unlink(e.path)
        except OSError:
            pass


def context(hits):
    lines = ["Anamnesis recall — memories that may bear on this prompt (descriptions only; "
             "read the file if it's relevant, ignore it if not):"]
    for _, name, typ, desc, path in hits:
        lines.append(f"- {name} ({typ or '?'}) — {desc}\n  {path}")
    return "\n".join(lines)


def _floor():
    try:
        return float(os.environ.get("ANAMNESIS_RECALL_FLOOR", FLOOR))
    except ValueError:
        return FLOOR


def main():
    data = json.load(sys.stdin)
    prompt = (data.get("prompt") or "").strip()
    if prompt.startswith("/") or len(prompt.split()) < MIN_WORDS:
        return
    memdir = MEMORY_DIR
    if not os.path.isdir(memdir):
        return
    session = str(data.get("session_id") or "none")
    state = os.environ.get("ANAMNESIS_RECALL_STATE") or os.path.join(memdir, ".index", "recall-seen")
    files = load_corpus(memdir, os.path.join(memdir, ".index", "recall-cache.json"))
    hits = rank(prompt, files, skip=core_names(memdir) | load_seen(state, session), floor=_floor())
    if not hits:
        return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": context(hits)}}), flush=True)
    save_seen(state, session, [h[1] for h in hits])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
