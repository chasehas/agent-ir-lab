#!/usr/bin/env bash
# Worked examples 2-4 capture: run the three example agent runs with collectors on.
# Same approach as scenarios/01-build-cache/build/capture.sh.
#
# Usage (from the repo root, Linux or WSL, user in the docker group):
#   examples/build/capture.sh [--auditd] [--gap SECONDS] [--out DIR]
#
# Use a throwaway machine. --auditd rotates the host's audit log and adds two
# audit rules for the run (removed again at the end; other rules are left alone).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$HERE/out/$(date -u +%Y%m%dT%H%M%SZ)"
GAP=30
AUDITD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --auditd) AUDITD=1 ;;
    --gap) GAP="$2"; shift ;;
    --out) OUT="$2"; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

VENV="${AGENT_IR_VENV:-$HOME/.venvs/agent-ir-lab}"
export PATH="$VENV/bin:$PATH"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
if [ "$(id -u)" = 0 ]; then
  export AGENT_OUTPUT_DIR="${AGENT_OUTPUT_DIR:-/srv/agent-output}"
else
  export AGENT_OUTPUT_DIR="${AGENT_OUTPUT_DIR:-$HOME/lab/srv/agent-output}"
fi
FALCO_SHIM="$REPO/scenarios/01-build-cache/build/falco/nomemlock.so"

mkdir -p "$OUT"/{transcripts,platform,host,network,services}
echo "output: $OUT"

PIDS=()
# The lab's own audit rules. Only these are added and removed; the host's other rules are untouched.
audit_rules() {  # $1: -a/-w to add, -d/-W to delete
  local exec_op=$1 watch_op
  case "$1" in -a) watch_op=-w ;; -d) watch_op=-W ;; esac
  auditctl "$exec_op" always,exit -F arch=b64 -S execve -k agent_exec
  auditctl "$watch_op" "$AGENT_OUTPUT_DIR" -p wa -k agent_output
}
cleanup() {
  set +e
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null; done
  docker stop -t 10 lab-zeek lab-falco >/dev/null 2>&1
  docker rm -f lab-zeek lab-falco lab-orders >/dev/null 2>&1
  if [ "$AUDITD" = 1 ]; then audit_rules -d >/dev/null 2>&1; fi
}
trap cleanup EXIT
# Stop if a collector isn't running, rather than produce evidence with a gap in it.
check_collectors() {
  local c
  for c in lab-falco lab-zeek; do
    if [ "$(docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null)" != true ]; then
      echo "collector $c is not running; stopping. Its last log lines:" >&2
      docker logs --tail 20 "$c" >&2 2>&1 || true
      exit 1
    fi
  done
}

echo "== images, network, service, output folder"
BUILD_ARGS=(--build-arg "PIP_INSTALL_OPTS=${PIP_INSTALL_OPTS:-}")
docker build -q -t lab/agent-sandbox:1 "$HERE/sandbox-image" >/dev/null
docker build -q "${BUILD_ARGS[@]}" -t lab/orders-service:1 "$HERE/service" >/dev/null
docker network inspect lab >/dev/null 2>&1 || \
  docker network create --opt com.docker.network.bridge.name=br-lab lab >/dev/null
docker rm -f lab-orders >/dev/null 2>&1 || true
mkdir -p "$OUT/services/orders-logs"
docker run -d --name lab-orders --network lab --network-alias orders.internal \
  -v "$OUT/services/orders-logs:/logs" lab/orders-service:1 >/dev/null
rm -rf "$AGENT_OUTPUT_DIR"
mkdir -p "$AGENT_OUTPUT_DIR"

echo "== starting collectors"
docker events --format '{{json .}}' > "$OUT/platform/docker-events.jsonl" &
PIDS+=($!)
(
  seen=" "
  while true; do
    for id in $(docker ps -q --no-trunc --filter ancestor=lab/agent-sandbox:1); do
      case "$seen" in *" $id "*) continue ;; esac
      docker inspect "$id" > "$OUT/platform/docker-inspect-${id:0:12}.json" && seen="$seen$id "
    done
    sleep 0.5
  done
) &
PIDS+=($!)

docker rm -f lab-falco >/dev/null 2>&1 || true
FALCO_EXTRA=()
if [ -f "$FALCO_SHIM" ]; then
  FALCO_EXTRA=(-e LD_PRELOAD=/shim/nomemlock.so -v "$FALCO_SHIM:/shim/nomemlock.so:ro")
fi
docker run -d --name lab-falco --hostname ci-runner-01 --privileged --pid=host "${FALCO_EXTRA[@]}" \
  -v /var/run/docker.sock:/host/var/run/docker.sock \
  -v /proc:/host/proc:ro -v /etc:/host/etc:ro \
  -v "$HERE/falco/agent_sandbox_rules.yaml:/etc/falco/rules.d/agent_sandbox_rules.yaml:ro" \
  -v "$OUT/host:/out" \
  falcosecurity/falco:latest \
  falco -o engine.kind=modern_ebpf -o json_output=true \
        -o file_output.enabled=true -o file_output.filename=/out/falco.jsonl \
        -r /etc/falco/falco_rules.yaml -r /etc/falco/rules.d/agent_sandbox_rules.yaml >/dev/null

docker rm -f lab-zeek >/dev/null 2>&1 || true
mkdir -p "$OUT/network/zeek"
docker run -d --name lab-zeek --net=host --cap-add=NET_RAW --cap-add=NET_ADMIN \
  -v "$OUT/network/zeek:/logs" -w /logs zeek/zeek:latest \
  zeek -C -i br-lab LogAscii::use_json=T >/dev/null

if [ "$AUDITD" = 1 ]; then
  kill -USR1 "$(pgrep -x auditd)"   # rotate, so the copied audit.log starts with this capture
  sleep 1
  audit_rules -d >/dev/null 2>&1 || true   # left over from an interrupted run
  audit_rules -a
fi

echo "== waiting for Falco"
falco_ready=0
for _ in $(seq 1 60); do
  if docker logs lab-falco 2>&1 | grep -q "Opening 'syscall' source"; then falco_ready=1; break; fi
  sleep 1
done
if [ "$falco_ready" != 1 ]; then
  echo "Falco didn't start within 60 seconds; stopping. Its last log lines:" >&2
  docker logs --tail 20 lab-falco >&2 2>&1 || true
  exit 1
fi
sleep 5
check_collectors

cd "$REPO"
for t in ex-lint-todos ex-status-report ex-copy-artifacts; do
  echo "== run: $t"
  inspect eval "examples/build/task.py@$t" --log-dir "$OUT/transcripts" --display plain | tail -2
  [ "$t" = ex-copy-artifacts ] || sleep "$GAP"
done
sleep 5
check_collectors

echo "== stopping collectors"
cleanup
trap - EXIT
if [ "$AUDITD" = 1 ]; then
  cp /var/log/audit/audit.log "$OUT/host/audit.log"
  ausearch -if "$OUT/host/audit.log" -i > "$OUT/host/audit-interpreted.txt" 2>/dev/null || true
fi
cp "$HERE"/compose-*.yaml "$OUT/platform/"
cp "$OUT/services/orders-logs/access.log" "$OUT/services/orders-access.log" 2>/dev/null || true
ls -la "$AGENT_OUTPUT_DIR" > "$OUT/host/agent-output-listing.txt"
echo "== done: $OUT"
find "$OUT" -type f | sort
