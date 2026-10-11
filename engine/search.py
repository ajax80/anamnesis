import os, re, sys, math, numpy as np
from collections import Counter
from mem_common import MEMORY_DIR, parse_file, is_active, memory_files
from indexer import connect, from_blob, reindex, DB_PATH
from embed import embed as default_embed

RRF_K = 60
LINK_RE = re.compile(r"\[\[([A-Za-z0-9_-]+)\]\]")


def _terms(q):
    return [t for t in re.split(r"\s+", q.lower()) if t]


def _tokens(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def bm25_rank(query, docs, k1=1.5, b=0.75):
    toks = {p: _tokens(t) for p, t in docs.items()}
    n = len(toks) or 1
    avg = sum(len(t) for t in toks.values()) / n or 1
    df = Counter(w for t in toks.values() for w in set(t))
    q = set(_tokens(query))
    scores = {}
    for p, t in toks.items():
        tf = Counter(t)
        sc = 0.0
        for w in q:
            if tf[w]:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                sc += idf * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * len(t) / avg))
        if sc > 0:
            scores[p] = sc
    return sorted(scores, key=scores.get, reverse=True)


def search(query, top=5, con=None, embed_fn=default_embed, memdir=MEMORY_DIR, include_archived=False):
    con = con or connect()
    rows = {r[0]: r for r in con.execute("SELECT path,name,type,description,embedding FROM mem")}
    meta, docs = {}, {}
    for path in memory_files(memdir):
        rec = parse_file(path)
        if not include_archived and not is_active(rec):
            continue                          # superseded/archived: hidden from default recall
        meta[path] = (rec["name"] or os.path.basename(path)[:-3], rec["type"], rec["description"] or "")
        docs[path] = f"{meta[path][0]} {meta[path][0]} {meta[path][2]} {rec['body']}"
    rankings = [bm25_rank(query, docs)]
    emb = [p for p in meta if p in rows]
    if emb:
        try:
            q = np.asarray(embed_fn(query), dtype=np.float32)
        except Exception as e:
            print(f"[anamnesis-search] semantic unavailable ({e}); keyword ranking only", file=sys.stderr)
        else:
            M = np.stack([from_blob(rows[p][4]) for p in emb])
            sims = (M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)) @ (q / (np.linalg.norm(q) + 1e-9))
            rankings.append([emb[i] for i in np.argsort(-sims)])
    fused = {}
    for ranking in rankings:
        for rank, path in enumerate(ranking):
            fused[path] = fused.get(path, 0.0) + 1.0 / (RRF_K + rank + 1)
    best = sorted(fused, key=fused.get, reverse=True)[:top]
    return [(fused[p] * RRF_K / len(rankings), *meta[p], p) for p in best]


def linked(path, memdir=MEMORY_DIR):
    out = []
    for slug in dict.fromkeys(LINK_RE.findall(parse_file(path)["raw"])):
        f = os.path.join(memdir, slug + ".md")
        if os.path.exists(f):
            out.append((slug, parse_file(f)["description"] or ""))
    return out


def grep_fallback(query, top=5, memdir=MEMORY_DIR, include_archived=False):
    index = os.path.join(memdir, "INDEX.md")
    terms = _terms(query)
    hits, in_archive = [], False
    if os.path.exists(index):
        for line in open(index, encoding="utf-8"):
            if line.startswith("## Archive"):
                in_archive = True
            if in_archive and not include_archived:
                continue
            low = line.lower()
            n = sum(1 for t in terms if t in low)
            if n:
                hits.append((n, line.strip()))
    hits.sort(key=lambda x: x[0], reverse=True)
    return hits[:top]


def format_result(score, name, typ, desc, path):
    return f"[{score:.2f}] {name} ({typ})\n       {desc}\n       {path}"


def run(query, top=5, include_archived=False, links=False):
    try:
        con = connect()
        reindex(con)                      # incremental refresh so results are never stale
        results = search(query, top=top, con=con, include_archived=include_archived)
        for r in results:
            print(format_result(*r))
            if links:
                for slug, desc in linked(r[4]):
                    print(f"         ↳ {slug} — {desc[:100]}")
    except Exception as e:                # Ollama down / any embed failure -> grep
        print(f"[anamnesis-search] semantic unavailable ({e}); grep fallback over INDEX.md:", file=sys.stderr)
        for n, line in grep_fallback(query, top=top, include_archived=include_archived):
            print(f"[{n}] {line}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("query"); ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--all", action="store_true", dest="include_archived",
                    help="include superseded/archived memories")
    ap.add_argument("--links", action="store_true", help="show 1-hop [[linked]] memories under each hit")
    a = ap.parse_args()
    run(a.query, a.top, a.include_archived, a.links)
