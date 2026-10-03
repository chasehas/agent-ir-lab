#!/usr/bin/env bash
# One-time (idempotent) setup of the Linux build venv inside WSL Ubuntu.
# Usage (from Windows): wsl -d Ubuntu -- bash /mnt/c/Users/<you>/Repos/agent-ir-lab/tools/wsl-setup.sh
set -euo pipefail
VENV="${AGENT_IR_VENV:-$HOME/.venvs/agent-ir-lab}"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q "inspect-ai==0.3.272"
"$VENV/bin/python" -c "import inspect_ai, sys; print('inspect-ai', inspect_ai.__version__, 'python', sys.version.split()[0])"
docker version --format 'docker server {{.Server.Version}}'
docker compose version
