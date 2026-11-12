#!/usr/bin/env python3
# Miss log: a memory that should have come back and didn't, written down when
# noticed. With the prompt (--query) and the memory that answered it (--found),
# each entry is a standing regression test: maint re-runs prompt recall on the
# query and reports the misses it still makes.
#   misses.py log <node> <what was missed> [--query Q] [--found SLUG]
#   misses.py check
import os, sys, time
from mem_common import parse_file, is_active

FILE = "_misses.md"
RECENT = 7 * 86400
HEADER = ("# Recall misses\n\n"
          "One line per miss: `- <time> | <node> | <found stem or -> | <query or -> | <what was missed>`.\n"
          "Written by `anamnesis miss`; maint re-checks the ones with a query and a stem.\n\n")


def _clean(s):
    # the record is |-separated; a | or newline inside a field would split it
    return " ".join((s or "").replace("|", "/").split())


def _stem(found):
    f = _clean(found).strip("[]")
    return f[:-3] if f.endswith(".md") else f


def log(memdir, node, text, query="", found="", now=None):
    now = now if now is not None else time.time()
    found = _stem(found)
    path = os.path.join(memdir, FILE)
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(HEADER)
        f.write("- %s | %s | %s | %s | %s\n" % (time.strftime("%Y-%m-%dT%H:%M", time.localtime(now)),
                _clean(node), _clean(found) or "-", _clean(query) or "-", _clean(text)))


def entries(memdir):
    out = []
    try:
        lines = open(os.path.join(memdir, FILE), encoding="utf-8").read().splitlines()
    except OSError:
        return out
    for line in lines:
        if not line.startswith("- "):
            continue
        parts = [p.strip() for p in line[2:].split(" | ", 4)]
        if len(parts) != 5:
            continue
        t, node, found, query, text = parts
        try:
            ts = time.mktime(time.strptime(t, "%Y-%m-%dT%H:%M"))
        except ValueError:
            continue
        out.append({"time": ts, "node": node, "found": "" if found == "-" else found,
                    "query": "" if query == "-" else query, "text": text})
    return out


def check(memdir, now=None):
    now = now if now is not None else time.time()
    warn, note = [], []
    es = entries(memdir)
    if not es:
        return warn, note
    recent = sum(1 for e in es if now - e["time"] <= RECENT)
    if recent:
        note.append(f"{recent} recall miss(es) logged in the last 7 days ({FILE}).")
    import recall
    files = None
    still = []
    for e in es:
        if not (e["found"] and e["query"]):
            continue
        path = os.path.join(memdir, e["found"] + ".md")
        if not os.path.exists(path):
            warn.append(f"{FILE}: miss names '{e['found']}', but {e['found']}.md doesn't exist.")
            continue
        rec = parse_file(path)
        if not is_active(rec):
            # recall never offers a retired memory: re-checking it could never clear
            by = rec.get("superseded_by") or "nothing"
            warn.append(f"{FILE}: miss names '{e['found']}', which is retired (superseded by {by}) — "
                        "re-log it against the successor, or delete the line.")
            continue
        if files is None:
            files = recall.load_corpus(memdir, os.path.join(memdir, ".index", "recall-cache.json"))
        # CORE and once-per-session skips left out: the question is whether it ranks
        if e["found"] not in [h[1] for h in recall.rank(e["query"], files, floor=recall._floor())]:
            still.append(e["found"])
    if still:
        note.append(f"prompt recall still misses {len(still)} logged case(s): {', '.join(dict.fromkeys(still))} "
                    "— sharpen those descriptions, or the floor.")
    return warn, note


if __name__ == "__main__":
    from mem_common import MEMORY_DIR
    if sys.argv[1] == "log":
        import argparse
        ap = argparse.ArgumentParser(prog="anamnesis miss")
        ap.add_argument("node"); ap.add_argument("text")
        ap.add_argument("--query", default=""); ap.add_argument("--found", default="")
        a = ap.parse_args(sys.argv[2:])
        log(MEMORY_DIR, a.node, a.text, a.query, a.found)
    elif sys.argv[1] == "check":
        w, n = check(MEMORY_DIR)
        for x in w: print("WARN " + x)
        for x in n: print("NOTE " + x)
