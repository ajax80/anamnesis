import os, re, sys, numpy as np
from mem_common import MEMORY_DIR
from indexer import connect, from_blob, reindex, DB_PATH
from embed import embed as default_embed

BOOST = 0.15


def _terms(q):
    return [t for t in re.split(r"\s+", q.lower()) if t]


def search(query, top=5, con=None, embed_fn=default_embed, memdir=MEMORY_DIR):
    con = con or connect()
    rows = con.execute("SELECT path,name,type,description,embedding FROM mem").fetchall()
    if not rows:
        return []
    q = np.asarray(embed_fn(query), dtype=np.float32)
    M = np.stack([from_blob(r[4]) for r in rows])
    qn = q / (np.linalg.norm(q) + 1e-9)
    Mn = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
    sims = Mn @ qn
    order = np.argsort(-sims)
    terms = _terms(query)
    cand = order[: max(top * 4, 20)]
    scored = []
    for i in cand:
        path, name, typ, desc, _ = rows[i]
        score = float(sims[i])
        hay = f"{name} {desc}".lower()
        if os.path.exists(path):
            try: hay += " " + open(path, encoding="utf-8").read().lower()
            except OSError: pass
        if any(t in hay for t in terms):
            score += BOOST
        scored.append((score, name, typ, desc, path))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top]


def grep_fallback(query, top=5, memdir=MEMORY_DIR):
    index = os.path.join(memdir, "INDEX.md")
    terms = _terms(query)
    hits = []
    if os.path.exists(index):
        for line in open(index, encoding="utf-8"):
            low = line.lower()
            n = sum(1 for t in terms if t in low)
            if n:
                hits.append((n, line.strip()))
    hits.sort(key=lambda x: x[0], reverse=True)
    return hits[:top]


def format_result(score, name, typ, desc, path):
    return f"[{score:.2f}] {name} ({typ})\n       {desc}\n       {path}"


def run(query, top=5):
    try:
        con = connect()
        reindex(con)                      # incremental refresh so results are never stale
        results = search(query, top=top, con=con)
        for r in results:
            print(format_result(*r))
    except Exception as e:                # Ollama down / any embed failure -> grep
        print(f"[anamnesis-search] semantic unavailable ({e}); grep fallback over INDEX.md:", file=sys.stderr)
        for n, line in grep_fallback(query, top=top):
            print(f"[{n}] {line}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query"); ap.add_argument("--top", type=int, default=5)
    a = ap.parse_args()
    run(a.query, a.top)
