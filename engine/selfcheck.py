import os, re, sys
from mem_common import MEMORY_DIR, memory_files, parse_file, sha256_file
from indexer import connect


def check(memdir=MEMORY_DIR, node=None):
    warn, note = [], []
    files = memory_files(memdir)
    index = os.path.join(memdir, "INDEX.md")
    listed = open(index, encoding="utf-8").read() if os.path.exists(index) else ""
    missing = [os.path.basename(p) for p in files if f"`{os.path.basename(p)}`" not in listed]
    if missing:
        warn.append(f"INDEX.md missing {len(missing)} file(s) (e.g. {', '.join(missing[:3])}) — genindex not running?")
    con = connect()
    db = dict(con.execute("SELECT path, sha FROM mem").fetchall())
    stale = [p for p in files if db.get(p) != sha256_file(p)]
    if stale:
        warn.append(f"embeddings stale/missing for {len(stale)} file(s) — indexer not running or embed backend down.")
    try:
        from search import search
        probe = next((p for p in files if (parse_file(p)["description"] or "").strip()), None)
        if probe:
            rec = parse_file(probe)
            hits = [h[4] for h in search(rec["description"], top=3, con=con)]
            if probe not in hits:
                warn.append(f"search smoke test: '{os.path.basename(probe)}' not in top 3 for its own description.")
    except Exception as e:
        warn.append(f"semantic search BROKEN: {type(e).__name__}: {e}")
    terms_file = os.path.join(memdir, "_retired_terms.txt")
    if os.path.exists(terms_file):
        surfaces = {"MEMORY.md": os.path.join(memdir, "MEMORY.md")}
        if node:
            surfaces[f"NOW.{node}.md"] = os.path.join(memdir, f"NOW.{node}.md")
        texts = {k: open(v, encoding="utf-8").read() for k, v in surfaces.items() if os.path.exists(v)}
        for p in files:
            rec = parse_file(p)
            if rec["status"] == "active" and rec["description"]:
                texts[os.path.basename(p) + " (description)"] = rec["description"]
        for line in open(terms_file, encoding="utf-8"):
            if line.lstrip().startswith("#"):
                continue
            spec, _, ok = line.partition("| ok:")
            term = spec.split(" — ")[0].strip()
            allowed = {x.strip() for x in ok.split(",") if x.strip()}
            if not term:
                continue
            rx = re.compile(r"(?<![\w.])" + re.escape(term) + r"(?![\w])", re.I)
            hits = [k for k, t in texts.items() if rx.search(t) and k.split(".md")[0] not in allowed and k.split(" ")[0] not in allowed]
            if hits:
                note.append(f"retired term '{term}' still in present-tense text: {', '.join(hits[:4])}" + (f" +{len(hits)-4}" if len(hits) > 4 else ""))
    return warn, note


if __name__ == "__main__":
    w, n = check(node=sys.argv[1] if len(sys.argv) > 1 else None)
    for x in w: print("WARN " + x)
    for x in n: print("NOTE " + x)
