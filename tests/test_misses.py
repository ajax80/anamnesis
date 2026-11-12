#!/usr/bin/env python3
# Miss log: a recall failure, written down when noticed, becomes a standing
# regression test — maint re-runs prompt recall on the logged query and says
# whether the memory still doesn't come back.
import os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine"))
import misses, mem_common

DAY = 86400


def write(memdir, name, desc, body="body"):
    with open(os.path.join(memdir, f"{name}.md"), "w") as f:
        f.write(f"---\nname: {name}\ndescription: {desc}\nmetadata:\n  type: project\n---\n{body}\n")


def corpus(d):
    write(d, "van_brakes", "minivan low brake pedal, master cylinder suspected")
    write(d, "garden", "tomato garden watering schedule")
    write(d, "udev", "native uevent daemon, rules reload")
    write(d, "cat", "biscuit the speckled stray cat")


def test_log_round_trip(d):
    misses.log(d, "alpha", "forgot the brake test plan", query="did dad win the bid | ebay",
               found="van_brakes", now=100 * DAY)
    (e,) = misses.entries(d)
    assert e["node"] == "alpha" and e["found"] == "van_brakes" and e["text"] == "forgot the brake test plan"
    assert e["query"] == "did dad win the bid / ebay", "a | in the query must not split the record"


def test_misses_file_not_a_memory(d):
    corpus(d)
    misses.log(d, "alpha", "x", now=100 * DAY)
    assert not any(p.endswith("_misses.md") for p in mem_common.memory_files(d))


def test_check_counts_recent_and_rechecks(d):
    os.environ["ANAMNESIS_RECALL_FLOOR"] = "1"
    try:
        _rechecks(d)
    finally:
        del os.environ["ANAMNESIS_RECALL_FLOOR"]


def _rechecks(d):
    corpus(d)
    misses.log(d, "alpha", "brakes not recalled", query="what about the minivan brake pedal master cylinder",
               found="van_brakes", now=100 * DAY)
    misses.log(d, "alpha", "garden not recalled", query="what should we plant this weekend",
               found="garden", now=100 * DAY)
    misses.log(d, "alpha", "old one", now=80 * DAY)
    warn, note = misses.check(d, now=101 * DAY)
    text = " ".join(note)
    assert "2 recall miss" in text, note
    assert "garden" in text and "still" in text, note
    assert "van_brakes" not in text, "a miss recall now catches is still reported"


def test_found_slug_missing_warned(d):
    corpus(d)
    misses.log(d, "alpha", "x", query="anything at all here", found="no_such_memory", now=100 * DAY)
    warn, _ = misses.check(d, now=100 * DAY)
    assert any("no_such_memory" in w for w in warn), warn


def test_found_normalized(d):
    misses.log(d, "alpha", "x", query="q here", found="[[van_brakes.md]]", now=100 * DAY)
    misses.log(d, "alpha", "y", query="q here", found="van_brakes.md", now=100 * DAY)
    assert [e["found"] for e in misses.entries(d)] == ["van_brakes", "van_brakes"]


def test_retired_found_reported_not_rechecked(d):
    corpus(d)
    with open(os.path.join(d, "old.md"), "w") as f:
        f.write("---\nname: old\ndescription: minivan brake notes\nstatus: superseded\n"
                "superseded_by: van_brakes\n---\nx\n")
    misses.log(d, "alpha", "x", query="minivan brake notes again please", found="old", now=100 * DAY)
    warn, note = misses.check(d, now=100 * DAY)
    assert not any("still misses" in n for n in note), note
    assert any("old" in w and "retired" in w and "van_brakes" in w for w in warn), warn


def test_no_log_is_quiet(d):
    assert misses.check(d, now=100 * DAY) == ([], [])


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
