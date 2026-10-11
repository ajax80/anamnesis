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
  <img src="https://img.shields.io/badge/semantic-Ollama%20nomic--embed--text-black.svg" alt="semantic">
</p>

---

> *anamnesis* (ἀνάμνησις) — recollection; the remembering that makes the past
> present.

An AI assistant with no memory re-derives who you are every session. Anamnesis
gives it a durable, human-readable memory that lives in a directory **you**
control, under git, and that you can read, grep, and edit by hand. The engine is
small and auditable. Every layer is optional: run the whole thing with nothing
but `grep`, and add semantic search only if you want it.

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
| **3 · Semantic** | `anamnesis search "…"` — embedding similarity when you don't know the keyword | a local model |

Plus a **live-state pointer** (`NOW.<node>.md`) injected at every session start,
optional **fleet sync** over a git remote, and a nightly **self-audit**. See
[`docs/DESIGN.md`](docs/DESIGN.md) and [`docs/FORMAT.md`](docs/FORMAT.md).

**Retiring a fact — supersession, not decay.** When something stops being true,
set `status: superseded` (with an optional `superseded_by:`) in its frontmatter.
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

# Tiers 1–2 (grep-only, no model): just pyyaml
python3 -m pip install -r requirements.txt

# Tier 3 (semantic recall): a running Ollama + an embedding model
ollama pull nomic-embed-text
# ...or no daemon at all: in-process embeddings via fastembed
#   pip install fastembed   and set ANAMNESIS_EMBED_BACKEND=fastembed

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
anamnesis config                   # show resolved configuration
```

### Wire it into Claude Code

Point a SessionStart hook at [`hooks/session-start.sh`](hooks/session-start.sh)
(see [`hooks/settings.snippet.json`](hooks/settings.snippet.json)). It prints
your CORE, the live-state pointer, and the last maintenance report into context,
then runs a throttled maintenance pass in the background. The format is a plain
directory of Markdown, so it works with any agent that can read files and shell
out.

## Dependencies

- **Tiers 1–2:** `bash`, `git`, `python3`, `pyyaml`. No network, no model.
- **Tier 3:** `numpy` + Ollama running `nomic-embed-text`. Pure HTTP — no torch,
  no GPU. Or `ANAMNESIS_EMBED_BACKEND=fastembed` for the same model in-process
  (ONNX, CPU) with no daemon.
- **Overnight changelog (optional):** `jq`, `curl`, any local chat model.

Each heavier layer degrades cleanly to a lighter one. Ollama down? Search falls
back to grep. No `jq`? The changelog becomes a file list.

## License

AGPL-3.0. See [LICENSE](LICENSE).
