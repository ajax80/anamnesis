#!/usr/bin/env python3
# Scratch ledger: notes written mid-session (SCRATCH.<node>.md). NOW is only
# rewritten at close-out, so without this a crash or a context compaction
# loses whatever was in flight. SessionStart prints it; close-out folds it
# into NOW and the memories, then clears it; maint flags notes left unfolded.
#   scratch.py add <node> <text> | show <node> | clear <node> | check <node>
import os, sys, time

STALE = 24 * 3600
STAMP = "%Y-%m-%d %H:%M"


def path(memdir, node):
    return os.path.join(memdir, f"SCRATCH.{node}.md")


def add(memdir, node, text, now=None):
    now = now if now is not None else time.time()
    p = path(memdir, node)
    new = not os.path.exists(p)
    with open(p, "a", encoding="utf-8") as f:
        if new:
            f.write(f"# SCRATCH — {node}\n\n_In-flight notes; fold into NOW + memories at close-out, then clear._\n\n")
        # one entry per line: continuation lines are indented under it
        body = "\n  ".join(l for l in text.strip().splitlines() if l.strip())
        f.write("- %s %s\n" % (time.strftime(STAMP, time.localtime(now)), body))


def show(memdir, node):
    try:
        with open(path(memdir, node), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def count(memdir, node):
    return sum(1 for l in show(memdir, node).splitlines() if l.startswith("- "))


def clear(memdir, node):
    try:
        os.unlink(path(memdir, node))
    except FileNotFoundError:
        pass


# age from the oldest note's own stamp: git rewrites the file's mtime on
# checkout/rebase, and every new note would push an mtime forward
def oldest(memdir, node):
    for l in show(memdir, node).splitlines():
        if l.startswith("- "):
            try:
                return time.mktime(time.strptime(l[2:18], STAMP))
            except ValueError:
                continue
    return None


def check(memdir, node, now=None):
    now = now if now is not None else time.time()
    n = count(memdir, node)
    if not n:
        return [], []
    first = oldest(memdir, node)
    age = now - (first if first is not None else os.stat(path(memdir, node)).st_mtime)
    if age <= STALE:
        return [], []
    shown = f"{int(age // 86400)}d" if age >= 48 * 3600 else f"{int(age // 3600)}h"
    return [f"SCRATCH.{node}.md holds {n} note(s), the oldest unfolded for {shown} — fold into "
            f"NOW/memories, then `anamnesis note --clear`."], []


if __name__ == "__main__":
    from mem_common import MEMORY_DIR
    cmd, node = sys.argv[1], sys.argv[2]
    if cmd == "add":
        add(MEMORY_DIR, node, " ".join(sys.argv[3:]))
    elif cmd == "show":
        sys.stdout.write(show(MEMORY_DIR, node))
    elif cmd == "clear":
        clear(MEMORY_DIR, node)
    elif cmd == "check":
        w, n = check(MEMORY_DIR, node)
        for x in w: print("WARN " + x)
