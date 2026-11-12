<p align="center">
  <img src="assets/anamnesis.jpg" alt="Anamnesis" width="640">
</p>

<p align="center">
  <b>Plain-text, git-native long-term memory for AI agents.</b><br>
  Your memories, your machine, your rules — no cloud, no closed engine,<br>
  no blob that reads everything you own.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License: AGPL-3.0"></a>
  <img src="https://img.shields.io/badge/deps-bash%20%C2%B7%20git%20%C2%B7%20python-lightgrey.svg" alt="deps">
  <img src="https://img.shields.io/badge/semantic-Ollama%20%7C%20fastembed-black.svg" alt="semantic">
</p>

---

> *anamnesis* (ἀνάμνησις) — recollection; the remembering that makes the past
> present.

An AI assistant with no memory re-derives who you are every session. Anamnesis
gives it a durable, human-readable memory that lives in a directory **you**
control, under git, and that you can read, grep, and edit by hand. The engine is
small and auditable. Every layer is optional: run the whole thing with nothing
but `grep` and keyword search, and add semantic search only if you want it.

<p align="center">
  <img src="assets/demo.svg" alt="anamnesis search demo" width="720">
</p>

## The hard line

**This repository is the engine. Your memories never go in it.** They live in
`$ANAMNESIS_DIR` — a private directory you control, synced (if at all) to a
remote *you* choose. Keep the machine public; keep the diary private.

## How it works — three tiers of recall

| Tier | What | Cost |
|------|------|------|
| **1 · CORE** | `MEMORY.md` — hand-curated identity, always loaded | free |
| **2 · INDEX** | `INDEX.md` — one line per memory, auto-derived from frontmatter, greppable | ~free |
| **3 · Search** | `anamnesis search "…"` — BM25 keyword ranking fused with embedding similarity (RRF): exact identifiers *and* meaning | keyword: free · semantic: a local model |
| **↺ Prompt recall** | a hook ranks every prompt against your memories and injects the top 3 *descriptions*: push, not pull, for the memory nobody thought to search for | free (~0.1s, no model) |

Plus a **live-state pointer** (`NOW.<node>.md`) injected at every session start,
optional **fleet sync** over a git remote, and a nightly **self-audit** that
checks its own health (see [Maintenance](#maintenance)). See
[`docs/DESIGN.md`](docs/DESIGN.md) and [`docs/FORMAT.md`](docs/FORMAT.md).

**Retiring a fact — supersession, not decay.** When something stops being true,
run `anamnesis retire <slug> --by <new-slug>` (or `--archive`), or set
`status: superseded` (with an optional `superseded_by:`) in its frontmatter by hand.
It drops out of the index and default search into an audit-only Archive, but the
file and its git history stay — a retired fact stays *visible and recoverable*
instead of silently winning a similarity score. `anamnesis search --all` brings
archived memories back. Nothing is inferred automatically; you (or a close-out
pass) decide — deliberately, because auto-detecting "this is stale now" is just
the unreliable-write problem in disguise.

A memory is one fact in one file:

```markdown
---
name: deploy-runbook
description: How we ship widget-service to prod — tag, CI gate, blue/green cutover
metadata:
  type: project
---

Ship from `main` only. Tag `vX.Y.Z`, wait for the CI gate, then `make deploy`
does the blue/green cutover. Roll back with `make deploy REF=<previous-tag>`.
Related: [[project-example]]
```

## Install

```bash
git clone https://github.com/ajax80/anamnesis ~/projects/anamnesis
cd ~/projects/anamnesis

# Core (index + keyword search, no model): pyyaml + numpy
python3 -m pip install -r requirements.txt

# Semantic search — pick ONE backend (or skip it; keyword search still works):
#   a) Ollama (a daemon you may already run):
ollama pull nomic-embed-text
#   b) fastembed (in-process, no daemon; ~520MB model fetched on first use):
python3 -m pip install -r requirements-fastembed.txt
#      then set ANAMNESIS_EMBED_BACKEND=fastembed in your config
#      (and ANAMNESIS_PYTHON if fastembed lives in a venv)

# Configure
mkdir -p ~/.config/anamnesis
cp anamnesis.env.example ~/.config/anamnesis/anamnesis.env
$EDITOR ~/.config/anamnesis/anamnesis.env     # set ANAMNESIS_DIR at least

# Put the CLI on PATH
ln -s ~/projects/anamnesis/bin/anamnesis ~/.local/bin/anamnesis
```

Then seed your memory directory from the samples:

```bash
mkdir -p ~/.anamnesis           # or wherever ANAMNESIS_DIR points
cp samples/MEMORY.md samples/*-example.md ~/.anamnesis/
cp samples/NOW.example.md ~/.anamnesis/NOW.$(hostname).md
cd ~/.anamnesis && git init      # your private memory repo
```

## Use

```bash
anamnesis genindex                 # (re)build INDEX.md from frontmatter
anamnesis search "how do we deploy" # hybrid recall: BM25 + semantic, fused (RRF)
anamnesis search "deploy" --links  # ...plus each hit's 1-hop [[linked]] memories
anamnesis retire old-runbook --by new-runbook   # supersede (or --archive)
anamnesis check                    # health: INDEX coverage, fresh embeddings, search smoke test
anamnesis maint                    # self-audit + changelog -> _maint.md
anamnesis sync                     # two-way fleet sync (if a hub remote is set)
anamnesis note "PR #12 open, CI pending"   # scratch ledger: survives a crash or compaction
anamnesis note --show | --clear    # ...read it back / clear it once folded into NOW
anamnesis miss "<what>" --query "<prompt>" --found <stem>   # log a recall miss
anamnesis config                   # show resolved configuration
```

### Maintenance

`anamnesis maint` (run nightly, or from the SessionStart hook with `--maybe`)
writes `_maint.md`: CORE size, INDEX regeneration, re-embedding, dead
`[[links]]`, a stale `NOW` pointer, and a health check (`anamnesis check`) that
fails loudly instead of rotting silently — INDEX missing files, stale
embeddings, a search smoke test, and any term listed in `_retired_terms.txt`
(`term — why | ok: slug, ...`) still appearing in CORE, NOW or an active
description. Add your own checks with `ANAMNESIS_MAINT_EXTRA`: any command
printing `WARN …` / `NOTE …` lines.

### Wire it into Claude Code

Point a SessionStart hook at [`hooks/session-start.sh`](hooks/session-start.sh)
(see [`hooks/settings.snippet.json`](hooks/settings.snippet.json)). It prints
your CORE, the live-state pointer, and the last maintenance report into context,
then runs a throttled maintenance pass in the background.

Point a UserPromptSubmit hook at [`hooks/prompt-recall.sh`](hooks/prompt-recall.sh)
too, and every prompt of four or more words is BM25-ranked against your memories.
The top three *descriptions* (never bodies) above a score floor are injected as
context, so a memory turns up even when nobody thought to search for it. Each
memory is offered at most once per session, and those CORE already links are
skipped. It needs no model and runs in about 0.1s warm, from a stat-keyed cache in
`.index/`. Anything that goes wrong prints nothing and exits 0, so it never
blocks a prompt. The floor (`ANAMNESIS_RECALL_FLOOR`, default 10) was calibrated
on a ~470-file brain. A small brain scores lower, so lower the floor there.

### Fleet health, recall misses, scratch

- **Fleet sync-health.** Each good two-way sync writes a heartbeat to the hub
  (`.fleet/<node>`, at most every 6h). `maint` warns about any node silent for 48h,
  and about this node's own last good sync. A node you retired: `git rm .fleet/<node>`.
- **Miss log.** `anamnesis miss "<what>" --query "<prompt>" --found <stem>` records a
  memory that should have come back and didn't (`_misses.md`). `maint` re-runs
  prompt recall on each logged query and lists the ones it still misses, so every
  miss becomes a regression test.
- **Scratch ledger.** `anamnesis note "<text>"` appends in-flight notes to
  `SCRATCH.<node>.md`. NOW is only rewritten at close-out, so this is what
  survives a crash or a context compaction. The SessionStart hook prints a leftover
  scratch; fold it into NOW at close-out, then `anamnesis note --clear`. `maint`
  flags notes left unfolded past 24h.

The format is a plain
directory of Markdown, so it works with any agent that can read files and shell
out.

### Adding a fleet node

Each node has its own clone of one private hub and runs the same engine:

```bash
git clone <hub> ~/.anamnesis                       # your hub, e.g. a bare repo on a LAN box
git -C ~/.anamnesis config user.name  "<node>"     # REQUIRED: with no identity every
git -C ~/.anamnesis config user.email "<node>@fleet.lan"   # auto-commit fails silently
# config: ANAMNESIS_NODE=<node>, ANAMNESIS_HUB_REMOTE=<hub>, and on every node
# but one, ANAMNESIS_INDEX_NODE=<that one> (one node regenerates INDEX + embeddings)
```

Then make sure it **syncs on a schedule**, not only when a session starts. A
backup node nobody opens otherwise drifts for weeks. A user timer works on
systemd, and any init that imports systemd user units:

```ini
# ~/.config/systemd/user/anamnesis-sync.service
[Service]
Type=oneshot
ExecStart=/bin/sh -c "%h/projects/anamnesis/bin/anamnesis-sync; %h/projects/anamnesis/bin/anamnesis-maint --maybe"

# ~/.config/systemd/user/anamnesis-sync.timer
[Timer]
OnBootSec=5min
OnUnitActiveSec=6h

[Install]
WantedBy=timers.target
```

`systemctl --user enable --now anamnesis-sync.timer`. Once the node's first
heartbeat lands in `.fleet/`, every node's `maint` will notice if it goes quiet.

## Dependencies

- **Core:** `bash`, `git`, `python3`, `pyyaml`, `numpy`. No network, no model —
  INDEX, grep and BM25 keyword search all work.
- **Semantic (optional):** Ollama running `nomic-embed-text` (pure HTTP), or
  `fastembed` for the same model in-process (ONNX, CPU, no daemon). No torch, no GPU.
- **Overnight changelog (optional):** `jq`, `curl`, any local chat model.

Each heavier layer degrades cleanly to a lighter one. Embed backend down? Search
keeps ranking by keyword. No `jq`? The changelog becomes a file list.

## License

AGPL-3.0. See [LICENSE](LICENSE).
