#!/usr/bin/env python3
# Scratch ledger: notes appended mid-session survive a crash or a context
# compaction (SessionStart prints them); close-out folds them into NOW and
# clears the file; maint flags notes left unfolded.
import os, sys, tempfile, subprocess

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import scratch, mem_common

H = 3600


def test_add_show_clear(d):
    scratch.add(d, "alpha", "PR #12 open, CI pending", now=1000 * H)
    scratch.add(d, "alpha", "next: rebase on main", now=1000 * H + 60)
    s = scratch.show(d, "alpha")
    assert s.index("PR #12 open") < s.index("next: rebase"), s
    assert scratch.count(d, "alpha") == 2
    scratch.clear(d, "alpha")
    assert scratch.show(d, "alpha") == "" and scratch.count(d, "alpha") == 0


def test_multiline_note_stays_one_entry(d):
    scratch.add(d, "alpha", "line one\nline two", now=1000 * H)
    assert scratch.count(d, "alpha") == 1


def test_per_node(d):
    scratch.add(d, "alpha", "a note", now=1000 * H)
    assert scratch.show(d, "beta") == ""


def test_not_a_memory(d):
    scratch.add(d, "alpha", "a note", now=1000 * H)
    assert mem_common.memory_files(d) == []


def test_stale_scratch_warned(d):
    scratch.add(d, "alpha", "a note", now=1000 * H)
    assert scratch.check(d, "alpha", now=1000 * H + 2 * H) == ([], [])
    warn, _ = scratch.check(d, "alpha", now=1000 * H + 30 * H)
    assert any("SCRATCH.alpha.md" in w and "1 note" in w for w in warn), warn


def test_age_is_the_oldest_note_not_mtime(d):
    # a note a day for a week, then git touching the file: still a week unfolded
    for day in range(7):
        scratch.add(d, "alpha", f"day {day}", now=1000 * H + day * 24 * H)
    p = scratch.path(d, "alpha")
    os.utime(p, None)
    warn, _ = scratch.check(d, "alpha", now=1000 * H + 6 * 24 * H + H)
    assert any("7 note" in w and "6d" in w for w in warn), warn


def test_session_start_prints_it(d):
    scratch.add(d, "alpha", "in flight: the slice PR", now=1000 * H)
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANAMNESIS")}
    env.update(ANAMNESIS_ENV=os.path.join(d, "none.env"), ANAMNESIS_DIR=d, ANAMNESIS_NODE="alpha",
               ANAMNESIS_BIN="/bin/true", HOME=d)
    p = subprocess.run([os.path.join(ROOT, "hooks", "session-start.sh")], env=env, capture_output=True, text=True)
    assert "in flight: the slice PR" in p.stdout, p.stdout


def test_cli(d):
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANAMNESIS")}
    env.update(ANAMNESIS_ENV=os.path.join(d, "none.env"), ANAMNESIS_DIR=d, ANAMNESIS_NODE="alpha", HOME=d)
    a = os.path.join(ROOT, "bin", "anamnesis")
    subprocess.run([a, "note", "from the cli"], env=env, check=True)
    p = subprocess.run([a, "note", "--show"], env=env, capture_output=True, text=True)
    assert "from the cli" in p.stdout, p.stdout
    subprocess.run([a, "note", "--clear"], env=env, check=True)
    assert scratch.count(d, "alpha") == 0


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
