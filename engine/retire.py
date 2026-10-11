import os, re, sys, argparse
from mem_common import MEMORY_DIR


def retire(slug, by=None, status="superseded", memdir=MEMORY_DIR):
    path = os.path.join(memdir, slug + ".md")
    if not os.path.exists(path):
        sys.exit(f"[anamnesis-retire] no such memory: {path}")
    if by and not os.path.exists(os.path.join(memdir, by + ".md")):
        sys.exit(f"[anamnesis-retire] successor not found: {by}.md")
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        text = f"---\nname: {slug}\n---\n" + text
    head, sep, rest = text[3:].partition("\n---")
    lines = [l for l in head.split("\n") if not re.match(r"(status|superseded_by):", l)]
    lines.insert(1, f"status: {status}")
    if by:
        lines.insert(2, f"superseded_by: {by}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("---" + "\n".join(lines) + sep + rest)
    print(f"[anamnesis-retire] {slug} → {status}" + (f" (by {by})" if by else ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("slug"); ap.add_argument("--by")
    ap.add_argument("--archive", action="store_true", help="status: archived (no successor)")
    a = ap.parse_args()
    retire(a.slug, a.by, "archived" if a.archive else "superseded")
