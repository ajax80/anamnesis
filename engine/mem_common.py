import os, glob, hashlib, yaml

MEMORY_DIR = os.environ.get(
    "ANAMNESIS_DIR", os.path.expanduser("~/.anamnesis")
)
_EXCLUDE_EXACT = {"INDEX.md", "_maint.md"}


def is_excluded(path):
    base = os.path.basename(path)
    if base in _EXCLUDE_EXACT or base == "MEMORY.md" or base.startswith("MEMORY.md."):
        return True
    if base.endswith(".md") and (base.startswith("NOW.") or base.startswith("NOW-")):
        return True
    return False


def memory_files(memdir=MEMORY_DIR):
    paths = [p for p in glob.glob(os.path.join(memdir, "*.md")) if not is_excluded(p)]
    return sorted(paths, key=lambda p: os.path.basename(p))


def _lenient_frontmatter(block):
    fm, meta = {}, {}
    for line in block.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, val = line.strip().partition(":")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key == "metadata":
            continue
        (meta if line.startswith((" ", "\t")) else fm)[key] = val
    if meta:
        fm["metadata"] = meta
    return fm


def parse_file(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                fm = _lenient_frontmatter(parts[1])
            body = parts[2]
    meta = (fm.get("metadata") or {}) if isinstance(fm, dict) else {}
    status = (fm.get("status") if isinstance(fm, dict) else None) or "active"
    return {
        "name": fm.get("name") if isinstance(fm, dict) else None,
        "type": meta.get("type") or (fm.get("type") if isinstance(fm, dict) else None),
        "description": fm.get("description") if isinstance(fm, dict) else None,
        "status": str(status).strip().lower(),
        "superseded_by": fm.get("superseded_by") if isinstance(fm, dict) else None,
        "body": body.strip(),
        "raw": text,
    }


ARCHIVED = ("superseded", "archived")


def is_active(rec):
    return rec.get("status", "active") not in ARCHIVED


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()
