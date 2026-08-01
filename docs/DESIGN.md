# Anamnesis — design

## Problem

An AI assistant with no persistent memory re-derives who you are every session.
Bolt-on "memory" products solve this by shipping a closed engine that ingests
your whole context and phones home. That trades one problem (forgetting) for a
worse one (an opaque blob that reads everything you have).

## Principle

Memory should be **plain text you own**, in a directory you control, under git.
The engine is small, auditable, and optional at every layer — you can run the
whole thing with nothing but `grep`, and add semantic recall only if you want
it. The data outlives any particular tool.

> **The hard line:** this repository is the *engine*. Your memories never live
> here. They live in `$ANAMNESIS_DIR` — a private directory, synced (if at all)
> to a remote *you* choose. Do not commit personal memory into this repo, and do
> not push a private memory directory to a public host.

## Architecture

```
$ANAMNESIS_DIR/                 ← your data (private, git-tracked, yours)
├── MEMORY.md                   Tier 1: hand-curated CORE, always loaded
├── INDEX.md                    Tier 2: auto-derived from frontmatter (greppable)
├── NOW.<node>.md               live-state pointer, one per node
├── _maint.md                   last maintenance report
├── <name>.md ...               one fact per file (user/feedback/project/reference)
└── .index/mem.db               Tier 3: disposable embedding cache (gitignored)

anamnesis (this repo)           ← the engine
├── bin/anamnesis               dispatcher: search|index|genindex|sync|maint
├── engine/*.py                 format parse, embed, index, search, genindex
└── hooks/                      SessionStart wiring for Claude Code
```

### Recall is tiered by cost

1. **CORE** — always in context (the SessionStart hook prints it). Free.
2. **INDEX** — one line per memory, regenerated from frontmatter. `grep` covers
   everything with no model in the loop.
3. **Semantic** — `nomic-embed-text` (via Ollama) over each memory's
   Title+Type+Description+body. Cosine similarity, with a keyword boost so exact
   term matches float up. Incremental: only changed files (by SHA) re-embed.
   If the embed backend is down, search degrades to grep over INDEX.

### Live state vs. long-term memory

`MEMORY.md` is slow-moving identity. `NOW.<node>.md` is the volatile "where were
we" pointer, rewritten every close-out and injected at the next session start.
Separating them keeps CORE stable and the working set current.

### Fleet

Multiple machines/agents share one memory over a git remote (`anamnesis sync`).
Each node has an identity (`ANAMNESIS_NODE`) and its own `NOW.<node>.md`.
Embeddings (`.index/`) are node-local and gitignored — each node rebuilds its
own cache; only the source `.md` files sync. One node can be designated to
regenerate `INDEX.md` (`ANAMNESIS_INDEX_NODE`) to avoid churn.

### Supersession, not decay

The hardest half of a memory system is the write side: deciding what to update,
retire, or forget. Age-based decay is the wrong tool — it buries the fact stated
once, early, and never repeated, which is often the one that matters most.

Anamnesis retires facts by **supersession**, applied by a human or a close-out
pass, never inferred automatically. A `status: superseded | archived` field
(with an optional `superseded_by` pointer) marks a memory retired. The status is
enforced at the **retrieval layer**, not by destroying the record: `genindex`
routes it to an Archive section, `search` hides it unless `--all` is passed, and
git retains the full history — so a retired fact is *visible and recoverable*,
never a silent similarity-score winner. Automatic contradiction detection is
deliberately out of scope; that would reintroduce the unreliable-write failure
mode this design exists to avoid.

### Maintenance

`anamnesis maint` (throttled to ~once/20h via `--maybe`) audits the merged
state: CORE size, INDEX regeneration, dead `[[link]]` targets, a stale `NOW`
pointer, and an optional local-LLM changelog of what changed overnight. It
writes `_maint.md`, which surfaces at the next session start.

## Dependencies

- **Tiers 1–2:** bash + git + python3 + `pyyaml`. No network, no model.
- **Tier 3 (semantic):** `numpy` + a running Ollama with `nomic-embed-text`.
  Pure HTTP; no torch, no GPU.
- **Changelog (optional):** `jq`, `curl`, any Ollama chat model.

Every heavier layer degrades cleanly to a lighter one.
