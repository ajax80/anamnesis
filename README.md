# Anamnesis

**Plain-text, git-native long-term memory for AI agents.** Your memories, your
machine, your rules — no cloud, no closed engine, no blob that reads everything
you own.

> *anamnesis* (ἀνάμνησις) — recollection; the remembering that makes the past
> present.

An AI assistant with no memory re-derives who you are every session. Anamnesis
gives it a durable, human-readable memory that lives in a directory **you**
control, under git, and that you can read, grep, and edit by hand. The engine is
small and auditable. Every layer is optional: run the whole thing with nothing
but `grep`, and add semantic search only if you want it.

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
anamnesis search "how do we deploy" # semantic recall (grep fallback if no model)
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
  no GPU.
- **Overnight changelog (optional):** `jq`, `curl`, any local chat model.

Each heavier layer degrades cleanly to a lighter one. Ollama down? Search falls
back to grep. No `jq`? The changelog becomes a file list.

## License

AGPL-3.0. See [LICENSE](LICENSE).
