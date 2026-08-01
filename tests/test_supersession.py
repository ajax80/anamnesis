#!/usr/bin/env python3
"""Supersession: a human-set `status` that the retrieval layer honors.
Superseded/archived memories drop out of INDEX's main list and out of default
search, but stay on disk (git = audit trail) and return with --all."""
import os, sys, tempfile, hashlib
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import mem_common, genindex, indexer, search


def write(memdir, name, desc, typ="project", status=None, superseded_by=None, body="body text here"):
    lines = ["---", f"name: {name}", f"description: {desc}"]
    if status:        lines.append(f"status: {status}")
    if superseded_by: lines.append(f"superseded_by: {superseded_by}")
    lines += ["metadata:", f"  type: {typ}", "---", "", body, ""]
    with open(os.path.join(memdir, f"{name}.md"), "w") as f:
        f.write("\n".join(lines))


def fake_embed(text):
    h = hashlib.sha256(text.encode()).digest()
    return np.frombuffer(h, dtype=np.uint8).astype("float32")[:16].tolist()


# --- tests ---------------------------------------------------------------

def test_status_defaults_active(memdir):
    write(memdir, "a", "A description long enough to pass lint")
    rec = mem_common.parse_file(os.path.join(memdir, "a.md"))
    assert rec["status"] == "active", f'expected active, got {rec.get("status")!r}'


def test_status_read_from_frontmatter(memdir):
    write(memdir, "b", "B description long enough to pass lint",
          status="superseded", superseded_by="a")
    rec = mem_common.parse_file(os.path.join(memdir, "b.md"))
    assert rec["status"] == "superseded", rec.get("status")
    assert rec["superseded_by"] == "a", rec.get("superseded_by")


def test_genindex_archives_superseded(memdir):
    write(memdir, "live", "Live memory description here ok now")
    write(memdir, "old", "Old memory description here ok now",
          status="superseded", superseded_by="live")
    content, _ = genindex.build_index(memdir)
    main, sep, archive = content.partition("## Archive")
    assert sep, "expected an '## Archive' section in INDEX content"
    assert "`live`" in main, "active memory must be in the main list"
    assert "`old`" not in main, "superseded memory must NOT be in the main list"
    assert "`old`" in archive, "superseded memory must appear in the Archive section"
    assert "live" in archive.split("`old`")[1][:80], "archive line should note superseded_by target"


def test_search_excludes_superseded_by_default(memdir):
    write(memdir, "live", "deploy widgets to prod runbook")
    write(memdir, "old", "deploy widgets to prod runbook",
          status="superseded", superseded_by="live")
    con = indexer.connect(os.path.join(memdir, ".index", "t.db"))
    indexer.reindex(con, memdir=memdir, embed_fn=fake_embed, rebuild=True)
    default = [r[1] for r in search.search("deploy widgets", con=con,
                                           embed_fn=fake_embed, memdir=memdir)]
    assert "old" not in default, f"superseded leaked into default search: {default}"
    assert "live" in default, f"active memory missing from search: {default}"
    allres = [r[1] for r in search.search("deploy widgets", con=con, embed_fn=fake_embed,
                                          memdir=memdir, include_archived=True)]
    assert "old" in allres, f"--all should surface superseded: {allres}"


# --- runner --------------------------------------------------------------

def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                t(d)
                print(f"  PASS {t.__name__}")
                passed += 1
            except Exception as e:
                print(f"  FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    main()
