#!/usr/bin/env bash
# Prepare a Claude Code cloud session (Ubuntu VM, root, no systemd) for capture runs.
# Idempotent. Run from the repo root as root: bash tools/cloud-setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# Docker: the daemon isn't started automatically in cloud sessions.
if ! docker info >/dev/null 2>&1; then
  (dockerd > /tmp/dockerd.log 2>&1 &)
  for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 1; done
fi
docker version --format 'docker server {{.Server.Version}}'

# auditd: no systemd, so start the daemon directly.
if ! command -v auditctl >/dev/null; then
  apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq auditd >/dev/null
fi
# The default 8 MB log rotates mid-capture on a busy VM, and capture.sh copies only
# the current audit.log. Raise the limit before starting the daemon.
sed -i 's/^max_log_file = .*/max_log_file = 200/' /etc/audit/auditd.conf
if pgrep -x auditd >/dev/null; then pkill -x auditd; sleep 1; fi
auditd
auditctl -s | head -3

# Falco memlock shim (see scenarios/01-build-cache/build/falco/nomemlock.c).
SHIM_DIR=scenarios/01-build-cache/build/falco
if [ ! -f "$SHIM_DIR/nomemlock.so" ]; then
  command -v gcc >/dev/null || (apt-get update -qq && apt-get install -y -qq gcc >/dev/null)
  gcc -shared -fPIC -O2 -o "$SHIM_DIR/nomemlock.so" "$SHIM_DIR/nomemlock.c" -ldl
fi

# Python venv with the pinned Inspect.
bash tools/wsl-setup.sh
