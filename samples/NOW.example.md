# NOW — live state pointer

> Smallest possible "where we are right now." Rewritten at each close-out and
> injected at every session start. If this is stale, say so. Copy this to
> `NOW.<your-node>.md` (e.g. `NOW.$(hostname).md`).

**Last updated:** 2026-01-01 — 🟢 Widget-service v2 API shipped and deployed.

## ▶️ Start here next session
1. Add pagination to `GET /widgets` (spec agreed, not yet implemented).
2. Investigate the flaky `test_widget_expiry` — fails ~1 in 20 runs.

## Left running / staged
- Staging deploy `staging-42` still up — tear down with `make staging-down`.
