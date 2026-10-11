import os, sys, sqlite3, numpy as np
from mem_common import MEMORY_DIR, memory_files, parse_file, sha256_file
from embed import build_payload, embed as default_embed

INDEX_DIR = os.path.join(MEMORY_DIR, ".index")
DB_PATH = os.path.join(INDEX_DIR, "mem.db")
SCHEMA = ("CREATE TABLE IF NOT EXISTS mem "
          "(path TEXT PRIMARY KEY, name TEXT, type TEXT, description TEXT, sha TEXT, embedding BLOB)")


def connect(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute(SCHEMA)
    return con


def to_blob(vec):  return np.asarray(vec, dtype=np.float32).tobytes()
def from_blob(b):  return np.frombuffer(b, dtype=np.float32)


def reindex(con, memdir=MEMORY_DIR, embed_fn=default_embed, rebuild=False):
    if rebuild:
        con.execute("DELETE FROM mem")
    existing = {r[0]: r[1] for r in con.execute("SELECT path, sha FROM mem")}
    seen, changed = set(), 0
    for path in memory_files(memdir):
        seen.add(path)
        sha = sha256_file(path)
        if not rebuild and existing.get(path) == sha:
            continue
        rec = parse_file(path)
        payload = build_payload(rec["name"] or os.path.basename(path),
                                rec["type"] or "?", rec["description"] or "", rec["body"])
        try:
            vec = embed_fn(payload)
        except Exception as e:
            print(f"[anamnesis-index] embed backend unavailable ({e}); embeddings not updated", file=sys.stderr)
            break
        con.execute("INSERT OR REPLACE INTO mem VALUES (?,?,?,?,?,?)",
                    (path, rec["name"], rec["type"], rec["description"], sha, to_blob(vec)))
        changed += 1
    for path in set(existing) - seen:
        con.execute("DELETE FROM mem WHERE path=?", (path,))
    con.commit()
    return changed


if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv[1:]
    con = connect()
    n = reindex(con, rebuild=rebuild)
    print(f"[anamnesis-index] re-embedded {n} file(s){' (full rebuild)' if rebuild else ''}")
