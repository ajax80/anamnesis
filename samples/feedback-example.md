---
name: feedback-example
description: Never force-push a shared branch — rebase locally and open a PR instead
metadata:
  type: feedback
---

Never `git push --force` a branch other people work from.

**Why:** it rewrites history others have already based work on, and silently
drops their commits. Cost their teammate half a day once.

**How to apply:** rebase locally, push to a fresh branch, open a PR. If a shared
branch truly must be rewritten, ask first and use `--force-with-lease`.
