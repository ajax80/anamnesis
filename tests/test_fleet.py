#!/usr/bin/env python3
# Fleet sync-health: each node's two-way sync leaves a throttled heartbeat in
# the hub (.fleet/<node>); maint flags any node silent for 48h, and this node's
# own last good sync.
import os, sys, time, tempfile, subprocess

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "engine"))
import fleet

H = 3600


def test_heartbeat_written_then_throttled(d):
    assert fleet.heartbeat(d, "alpha", now=1000 * H, head="abc123")
    line = open(os.path.join(d, ".fleet", "alpha")).read()
    assert line.split()[0] == str(1000 * H) and "abc123" in line, line
    assert not fleet.heartbeat(d, "alpha", now=1000 * H + 5 * H), "rewrote inside 6h"
    assert fleet.heartbeat(d, "alpha", now=1000 * H + 7 * H)


def test_silent_node_warned(d):
    fleet.heartbeat(d, "alpha", now=1000 * H)
    fleet.heartbeat(d, "beta", now=1000 * H - 50 * H)
    warn, note = fleet.check(d, "alpha", now=1000 * H)
    assert any("beta" in w and "2d" in w for w in warn), warn
    assert not any("alpha" in w for w in warn), warn
    assert any("alpha" in n and "beta" in n for n in note), note


def test_own_sync_failing_warned(d):
    fleet.heartbeat(d, "alpha", now=1000 * H)
    ok = os.path.join(d, "ok")
    open(ok, "w").close()
    os.utime(ok, (1000 * H - 60 * H, 1000 * H - 60 * H))
    warn, _ = fleet.check(d, "alpha", now=1000 * H, ok_stamp=ok)
    assert any("this node" in w for w in warn), warn
    warn, _ = fleet.check(d, "alpha", now=1000 * H, ok_stamp=os.path.join(d, "never"))
    assert any("this node" in w and "never" in w for w in warn), warn


def test_no_fleet_dir_is_quiet(d):
    assert fleet.check(d, "alpha", now=1000 * H) == ([], [])


def test_heartbeat_not_a_memory(d):
    import mem_common
    fleet.heartbeat(d, "alpha", now=1000 * H)
    assert mem_common.memory_files(d) == []


def git(cwd, *a):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


def test_sync_pushes_heartbeat_through_hub(d):
    hub = os.path.join(d, "hub.git")
    git(d, "init", "-q", "--bare", "-b", "main", hub)
    seed = os.path.join(d, "seed")
    git(d, "clone", "-q", hub, seed)
    open(os.path.join(seed, "a.md"), "w").write("---\nname: a\n---\nx\n")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "seed", "--allow-empty")
    git(seed, "add", "-A"); git(seed, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed2")
    git(seed, "push", "-q", "origin", "main")
    nodes = {}
    for n in ("alpha", "beta"):
        nodes[n] = os.path.join(d, n)
        git(d, "clone", "-q", hub, nodes[n])
        git(nodes[n], "config", "user.name", n); git(nodes[n], "config", "user.email", n + "@t")
    def sync(n):
        # config the way a real node has it: plain VAR= lines in an env file, run directly
        envf = os.path.join(d, n + ".env")
        with open(envf, "w") as f:
            f.write(f'ANAMNESIS_DIR="{nodes[n]}"\nANAMNESIS_NODE="{n}"\nANAMNESIS_HUB_REMOTE="{hub}"\n')
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANAMNESIS")}
        env.update(ANAMNESIS_ENV=envf, XDG_STATE_HOME=os.path.join(d, "state-" + n), HOME=d)
        p = subprocess.run([os.path.join(ROOT, "bin", "anamnesis-sync")], env=env, capture_output=True, text=True)
        assert p.returncode == 0, p.stderr
        return os.path.join(d, "state-" + n, "anamnesis", "sync-ok")
    ok = sync("alpha")
    assert os.path.exists(ok), "no local sync-ok stamp after a good sync"
    sync("beta")
    assert sorted(os.listdir(os.path.join(nodes["beta"], ".fleet"))) == ["alpha", "beta"]
    n_commits = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=nodes["beta"],
                               capture_output=True, text=True).stdout.strip()
    sync("beta")
    again = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=nodes["beta"],
                           capture_output=True, text=True).stdout.strip()
    assert n_commits == again, "a second sync inside 6h committed another heartbeat"


def test_failed_commit_is_not_a_good_sync(d):
    hub = os.path.join(d, "hub.git")
    git(d, "init", "-q", "--bare", "-b", "main", hub)
    node = os.path.join(d, "n")
    git(d, "clone", "-q", hub, node)
    git(node, "config", "user.name", "n"); git(node, "config", "user.email", "n@t")
    git(node, "commit", "-q", "--allow-empty", "-m", "seed"); git(node, "push", "-q", "origin", "main")
    hooks = os.path.join(node, ".git", "hooks", "pre-commit")
    with open(hooks, "w") as f:
        f.write("#!/bin/sh\nexit 1\n")
    os.chmod(hooks, 0o755)
    open(os.path.join(node, "x.md"), "w").write("edit\n")
    envf = os.path.join(d, "n.env")
    with open(envf, "w") as f:
        f.write(f'ANAMNESIS_DIR="{node}"\nANAMNESIS_NODE="n"\nANAMNESIS_HUB_REMOTE="{hub}"\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith("ANAMNESIS")}
    env.update(ANAMNESIS_ENV=envf, XDG_STATE_HOME=os.path.join(d, "st"), HOME=d)
    subprocess.run([os.path.join(ROOT, "bin", "anamnesis-sync")], env=env, capture_output=True)
    assert not os.path.exists(os.path.join(d, "st", "anamnesis", "sync-ok")), "sync-ok touched with edits stuck"


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
