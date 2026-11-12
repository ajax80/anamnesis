#!/usr/bin/env python3
"""Prompt-time recall hook: BM25 over the memory files, top descriptions
injected as UserPromptSubmit additionalContext. Never blocks a prompt."""
import os, sys, json, time, tempfile, subprocess

ENGINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine")
sys.path.insert(0, ENGINE)
import recall


def write(memdir, name, desc, body="body text here", status=None, typ="project"):
    lines = ["---", f"name: {name}", f"description: {desc}"]
    if status:
        lines.append(f"status: {status}")
    lines += ["metadata:", f"  type: {typ}", "---", "", body, ""]
    with open(os.path.join(memdir, f"{name}.md"), "w") as f:
        f.write("\n".join(lines))


def corpus(memdir):
    write(memdir, "van_brakes", "2000 Minivan low brake pedal, master cylinder suspected",
          body="Hold test: pedal sinks means master cylinder. Pump test: rises means air.")
    write(memdir, "schema_udev", "schema-udev native uevent daemon, rules reload keeps the live set")
    write(memdir, "cat_biscuit", "Biscuit the speckled stray cat", typ="user")
    write(memdir, "garden", "tomato garden notes, watering schedule")
    write(memdir, "old_brakes", "Minivan brake pedal master cylinder old notes", status="superseded")


def hook(memdir, prompt, session="s1", core=""):
    with open(os.path.join(memdir, "MEMORY.md"), "w") as f:
        f.write(core)
    env = dict(os.environ, ANAMNESIS_DIR=memdir, ANAMNESIS_RECALL_STATE=os.path.join(memdir, "state"),
               ANAMNESIS_RECALL_FLOOR="1")
    payload = prompt if not isinstance(prompt, str) or prompt.startswith("RAW:") else \
        json.dumps({"prompt": prompt, "session_id": session, "hook_event_name": "UserPromptSubmit"})
    if isinstance(payload, str) and payload.startswith("RAW:"):
        payload = payload[4:]
    p = subprocess.run([sys.executable, os.path.join(ENGINE, "recall.py")], input=payload,
                       capture_output=True, text=True, env=env, timeout=10)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)["hookSpecificOutput"]["additionalContext"] if p.stdout.strip() else ""


# --- tests ---------------------------------------------------------------

def test_relevant_prompt_injects_description_not_body(memdir):
    corpus(memdir)
    out = hook(memdir, "did the minivan brake pedal hold test happen yet")
    assert "van_brakes" in out and "master cylinder suspected" in out, out
    assert "Pump test" not in out, "body leaked into context"


def test_output_shape(memdir):
    corpus(memdir)
    env = dict(os.environ, ANAMNESIS_DIR=memdir, ANAMNESIS_RECALL_STATE=os.path.join(memdir, "state"),
               ANAMNESIS_RECALL_FLOOR="1")
    p = subprocess.run([sys.executable, os.path.join(ENGINE, "recall.py")],
                       input=json.dumps({"prompt": "minivan brake pedal master cylinder again", "session_id": "x"}),
                       capture_output=True, text=True, env=env)
    o = json.loads(p.stdout)["hookSpecificOutput"]
    assert o["hookEventName"] == "UserPromptSubmit" and o["additionalContext"], o


def test_short_prompt_skipped(memdir):
    corpus(memdir)
    assert hook(memdir, "minivan brakes?") == ""


def test_slash_command_skipped(memdir):
    corpus(memdir)
    assert hook(memdir, "/done minivan brake pedal master cylinder") == ""


def test_weak_match_injects_nothing(memdir):
    corpus(memdir)
    assert hook(memdir, "what do you think about that thing we said") == ""


def test_floor_filters(memdir):
    corpus(memdir)
    files = recall.load_corpus(memdir, os.path.join(memdir, ".index", "c.json"))
    q = "did the minivan brake pedal hold test happen yet"
    assert recall.rank(q, files, floor=1)
    assert recall.rank(q, files, floor=1e9) == []


def test_keyed_by_file_stem_not_name(memdir):
    # real brains: names with spaces, names that differ from the file stem
    corpus(memdir)
    with open(os.path.join(memdir, "fuel_relay.md"), "w") as f:
        f.write("---\nname: Fuel Pump — Minivan relay saga\ndescription: minivan fuel pump relay clicking diagnosis\n"
                "metadata:\n  type: project\n---\nbody\n")
    q = "minivan fuel pump relay clicking again today"
    out = hook(memdir, q, session="k")
    assert "fuel_relay" in out, out
    assert "fuel_relay" not in hook(memdir, q, session="k"), "multi-word name re-offered"
    assert "fuel_relay" not in hook(memdir, q, session="k2", core="- [[fuel_relay]]\n"), "CORE link by stem not skipped"


def test_one_bad_file_doesnt_kill_recall(memdir):
    corpus(memdir)
    with open(os.path.join(memdir, "latin1.md"), "wb") as f:
        f.write(b"---\nname: x\ndescription: caf\xe9\n---\nbody\n")
    with open(os.path.join(memdir, "scalar_meta.md"), "w") as f:
        f.write("---\nname: y\ndescription: z\nmetadata: 5\n---\nbody\n")
    assert "van_brakes" in hook(memdir, "did the minivan brake pedal hold test happen yet")


def test_bad_floor_falls_back(memdir):
    corpus(memdir)
    env = dict(os.environ, ANAMNESIS_DIR=memdir, ANAMNESIS_RECALL_STATE=os.path.join(memdir, "state"),
               ANAMNESIS_RECALL_FLOOR="ten")
    p = subprocess.run([sys.executable, os.path.join(ENGINE, "recall.py")],
                       input=json.dumps({"prompt": "minivan brake pedal master cylinder", "session_id": "x"}),
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0 and not p.stderr, (p.returncode, p.stderr)


def test_wrapper_exports_env_file(memdir):
    corpus(memdir)
    envf = os.path.join(memdir, "a.env")
    with open(envf, "w") as f:
        f.write(f'ANAMNESIS_DIR="{memdir}"\nANAMNESIS_RECALL_FLOOR="1e9"\nANAMNESIS_PYTHON="{sys.executable}"\n')
    q = json.dumps({"prompt": "did the minivan brake pedal hold test happen yet", "session_id": "w"})
    sh = os.path.join(ENGINE, "..", "hooks", "prompt-recall.sh")
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANAMNESIS")}
    env.update(ANAMNESIS_ENV=envf, HOME=memdir)
    p = subprocess.run([sh], input=q, capture_output=True, text=True, env=env)
    assert p.returncode == 0 and p.stdout == "", "env-file floor not honored: " + p.stdout
    with open(envf, "a") as f:
        f.write('ANAMNESIS_RECALL_FLOOR="1"\n')
    p = subprocess.run([sh], input=q, capture_output=True, text=True, env=env)
    assert "van_brakes" in p.stdout, p.stdout


def test_one_rare_word_is_enough(memdir):
    # "is biscuit alright" names one thing; a word five files share names nothing
    corpus(memdir)
    for i in range(5):
        write(memdir, f"pump_{i}", f"pool pump wiring notes part {i}")
    files = recall.load_corpus(memdir, os.path.join(memdir, ".index", "c.json"))
    assert [h[1] for h in recall.rank("is biscuit doing alright today", files, floor=1)] == ["cat_biscuit"]
    assert recall.rank("is the pump doing alright today", files, floor=1) == []


def test_superseded_never_recalled(memdir):
    corpus(memdir)
    assert "old_brakes" not in hook(memdir, "minivan brake pedal master cylinder old notes please")


def test_core_linked_skipped(memdir):
    corpus(memdir)
    out = hook(memdir, "did the minivan brake pedal hold test happen yet",
               core="- brakes → [[van_brakes]]\n")
    assert "van_brakes" not in out, out


def test_once_per_session(memdir):
    corpus(memdir)
    q = "did the minivan brake pedal hold test happen yet"
    assert "van_brakes" in hook(memdir, q, session="a")
    assert "van_brakes" not in hook(memdir, q, session="a")
    assert "van_brakes" in hook(memdir, q, session="b")


def test_top_three_at_most(memdir):
    corpus(memdir)   # words every doc shares have no idf
    for i in range(6):
        write(memdir, f"pump_{i}", f"pool pump wiring notes part {i}")
    out = hook(memdir, "pool pump wiring notes from last summer")
    assert sum(f"pump_{i}" in out for i in range(6)) == 3, out


def test_edit_seen_through_cache(memdir):
    corpus(memdir)
    hook(memdir, "tomato garden watering schedule this week", session="c1")
    time.sleep(0.01)
    write(memdir, "garden", "zucchini harvest log")
    out = hook(memdir, "zucchini harvest log for the season", session="c2")
    assert "garden" in out, out


def test_garbage_stdin_is_silent(memdir):
    corpus(memdir)
    assert hook(memdir, "RAW:not json at all") == ""
    assert hook(memdir, "RAW:" + json.dumps({"session_id": "x"})) == ""


def test_missing_memdir_is_silent(memdir):
    env = dict(os.environ, ANAMNESIS_DIR=os.path.join(memdir, "nope"),
               ANAMNESIS_RECALL_STATE=os.path.join(memdir, "state"),
               ANAMNESIS_RECALL_FLOOR="1")
    p = subprocess.run([sys.executable, os.path.join(ENGINE, "recall.py")],
                       input=json.dumps({"prompt": "minivan brake pedal master cylinder", "session_id": "x"}),
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0 and p.stdout == "", (p.returncode, p.stdout)


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
