#!/usr/bin/env bash
# Anamnesis prompt-time recall for Claude Code (UserPromptSubmit). Passes the
# hook JSON to engine/recall.py, which prints additionalContext JSON or nothing.
# Never blocks a prompt: a hang is cut at 2s and every failure exits 0.
set -uo pipefail

ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../engine" && pwd)"
for cfg in "${ANAMNESIS_ENV:-}" "$HOME/.config/anamnesis/anamnesis.env"; do
  # set -a: the env file's plain VAR= lines must reach recall.py
  [ -n "$cfg" ] && [ -f "$cfg" ] && { set -a; . "$cfg"; set +a; break; }
done
export ANAMNESIS_DIR="${ANAMNESIS_DIR:-$HOME/.anamnesis}"
timeout 2 env PYTHONPATH="$ENGINE" "${ANAMNESIS_PYTHON:-python3}" "$ENGINE/recall.py" 2>/dev/null
exit 0
