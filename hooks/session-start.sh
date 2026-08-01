#!/usr/bin/env bash
# Anamnesis SessionStart hook for Claude Code.
# Pulls the fleet, prints the live-state pointer (NOW.<node>.md) and the last
# maintenance report so they land in the model's context, then kicks off a
# throttled maintenance pass in the background. Wire it in via settings.json
# (see hooks/settings.snippet.json) or call it directly.
set -uo pipefail

ANAMNESIS_BIN="${ANAMNESIS_BIN:-$HOME/projects/anamnesis/bin/anamnesis}"
for cfg in "${ANAMNESIS_ENV:-}" "$HOME/.config/anamnesis/anamnesis.env"; do
  [ -n "$cfg" ] && [ -f "$cfg" ] && . "$cfg" && break
done
MEM="${ANAMNESIS_DIR:-$HOME/.anamnesis}"
NODE="${ANAMNESIS_NODE:-$(hostname)}"

timeout 12 "$ANAMNESIS_BIN" sync pull >/dev/null 2>&1

printf '=== NOW (live state, read this first) ===\n'
cat "$MEM/NOW.$NODE.md" 2>/dev/null || echo "(no NOW.$NODE.md yet — write one)"

if [ -f "$MEM/_maint.md" ]; then
  printf '\n=== last maintenance ===\n'
  cat "$MEM/_maint.md"
fi

( "$ANAMNESIS_BIN" maint --maybe >/dev/null 2>&1 & )
