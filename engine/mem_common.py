import os, glob, hashlib, yaml

MEMORY_DIR = os.environ.get(
    "ANAMNESIS_DIR", os.path.expanduser("~/.anamnesis")
)
_EXCLUDE_EXACT = {"MEMORY.md", "MEMORY.md.bak", "INDEX.md", "_maint.md"}


def is_excluded(path):
    base = os.path.basename(path)
    if base in _EXCLUDE_EXACT:
        return True
    if base.endswith(".md") and (base.startswith("NOW.") or base.startswith("NOW-")):
        return True
    return False


def memory_files(memdir=MEMORY_DIR):
    paths = [p for p in glob.glob(os.path.join(memdir, "*.md")) if not is_excluded(p)]
    return sorted(paths, key=lambda p: os.path.basename(p))


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
                fm = {}
            body = parts[2]
    meta = (fm.get("metadata") or {}) if isinstance(fm, dict) else {}
    status = (fm.get("status") if isinstance(fm, dict) else None) or "active"
    return {
        "name": fm.get("name") if isinstance(fm, dict) else None,
        "type": meta.get("type"),
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
