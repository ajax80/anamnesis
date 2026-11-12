#!/usr/bin/env python3
# Fleet sync-health. A node whose sync silently fails looks exactly like a node
# with nothing to say, so each good two-way sync leaves a heartbeat in the hub
# (.fleet/<node>: "<epoch> <iso> <host> <head>"), and maint flags any node
# silent for 48h. A retired node: git rm .fleet/<node>.
#   fleet.py heartbeat <node>   write it if older than 6h (prints "wrote" if so)
#   fleet.py ok <node>          stamp this node's last good two-way sync
#   fleet.py check <node>       WARN/NOTE lines for maint
import os, sys, time, socket, subprocess

BEAT_EVERY = 6 * 3600     # one commit per node per 6h at most, not one per sync
SILENT = 48 * 3600


def _dir(memdir):
    return os.path.join(memdir, ".fleet")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return int(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def heartbeat(memdir, node, now=None, host=None, head=""):
    now = int(now if now is not None else time.time())
    path = os.path.join(_dir(memdir), node)
    last = _read(path)
    if last is not None and now - last < BEAT_EVERY:
        return False
    os.makedirs(_dir(memdir), exist_ok=True)
    iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{now} {iso} {host or socket.gethostname()} {head or '-'}\n")
    return True


def _age(sec):
    return f"{sec // 86400}d" if sec >= 86400 else f"{sec // 3600}h"


def check(memdir, node, now=None, ok_stamp=None):
    now = int(now if now is not None else time.time())
    warn, note = [], []
    try:
        nodes = sorted(os.listdir(_dir(memdir)))
    except OSError:
        return warn, note
    seen = []
    for n in nodes:
        t = _read(os.path.join(_dir(memdir), n))
        if t is None:
            continue
        seen.append(f"{n} {_age(max(0, now - t))}")
        if n != node and now - t > SILENT:
            warn.append(f"fleet: node {n} last synced {_age(now - t)} ago — sync failing there, or retired "
                        f"(then git rm .fleet/{n}).")
    if ok_stamp is not None:
        try:
            age = now - int(os.stat(ok_stamp).st_mtime)
        except OSError:
            warn.append("fleet: this node has never completed a two-way sync (hub unreachable or push refused?).")
        else:
            if age > SILENT:
                warn.append(f"fleet: this node's last good two-way sync was {_age(age)} ago.")
    if seen:
        note.append("fleet heartbeats: " + ", ".join(seen))
    return warn, note


def ok_stamp_path():
    return os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
                        "anamnesis", "sync-ok")


if __name__ == "__main__":
    from mem_common import MEMORY_DIR
    cmd, node = sys.argv[1], sys.argv[2]
    if cmd == "heartbeat":
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=MEMORY_DIR,
                              capture_output=True, text=True).stdout.strip()
        if heartbeat(MEMORY_DIR, node, head=head):
            print("wrote")
    elif cmd == "ok":
        p = ok_stamp_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a"):
            os.utime(p, None)
    elif cmd == "check":
        w, n = check(MEMORY_DIR, node, ok_stamp=ok_stamp_path())
        for x in w: print("WARN " + x)
        for x in n: print("NOTE " + x)
