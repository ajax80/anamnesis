# The Anamnesis memory format

A memory is **one fact in one plain-text Markdown file**. Human-readable,
git-diffable, greppable, and portable. There is no database of record — the
files *are* the record. The `.index/` SQLite store is a disposable cache.

## A memory file

```markdown
---
name: <short-kebab-case-slug>
description: <one line — this is what recall matches against; make it count>
metadata:
  type: user | feedback | project | reference
---

<The fact. For feedback/project, follow with **Why:** and **How to apply:** lines.>
Link related memories with [[their-name]].
```

- `name` — stable slug, also the filename (`<name>.md`).
- `description` — the single most important field: the index and the first pass
  of semantic search rank on it. One dense, specific line.
- `metadata.type` — the memory's kind (see below). Drives how you write the body.
- `[[wikilinks]]` — cross-references by `name`. A link to a file that does not
  exist yet is fine; maintenance lists those as "todo candidates."

## Types

| type | what it holds |
|------|---------------|
| `user` | who the person is — role, history, preferences, the durable truths |
| `feedback` | how you should work — corrections and confirmed approaches, **with the why** |
| `project` | ongoing work, goals, constraints not derivable from the code/history |
| `reference` | pointers to external resources (URLs, dashboards, tickets) |

## Special files (not indexed as memories)

- **`MEMORY.md`** — Tier 1 CORE. Hand-curated, always loaded into context. The
  identity anchor plus a one-line map per cluster. Kept small (8KB target).
- **`INDEX.md`** — Tier 2. Auto-generated from every memory's frontmatter by
  `anamnesis genindex`. Complete, greppable, cheap. Never edit by hand.
- **`NOW.<node>.md`** — the live-state pointer for one node: the smallest
  possible "where we are right now," rewritten at each close-out and injected at
  session start. Each machine/agent in a fleet keeps its own.
- **`_maint.md`** — the last maintenance report.

## The three tiers of recall

1. **CORE** (`MEMORY.md`) — always in context. Zero lookup cost.
2. **INDEX** (`INDEX.md`) — `grep` it. Complete coverage, no model needed.
3. **Semantic** (`anamnesis search "…"`) — embedding similarity over bodies,
   for when you don't know the right keyword. Falls back to grep if the embed
   backend is offline.

Start at the cheapest tier that answers the question.
