#!/usr/bin/env bash
# Run a command from the repo root with the Linux build venv on PATH.
# Usage (from Windows): wsl -d Ubuntu --exec bash /mnt/c/Users/<you>/Repos/agent-ir-lab/tools/wsl-run.sh <command> [args...]
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${AGENT_IR_VENV:-$HOME/.venvs/agent-ir-lab}"
export PATH="$VENV/bin:$PATH"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
exec "$@"
