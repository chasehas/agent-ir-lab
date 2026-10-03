#!/usr/bin/env bash
# Recreate /srv/agent-output exactly as captured after the example runs
# (see examples/evidence/host/agent-output-listing.txt). Run once in WSL:
#   bash demo/setup-output.sh        (from the repo root; uses sudo)
# Demo reveal:  TZ=UTC ls -la /srv/agent-output
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT=/srv/agent-output
FIXTURE="$REPO/examples/build/fixtures/app-1.4.2.tar.gz"

# Everything that can fail is checked before $OUT is touched.
for cmd in sudo sha256sum; do
  command -v "$cmd" >/dev/null || { echo "setup-output.sh needs $cmd" >&2; exit 1; }
done
if [ ! -f "$FIXTURE" ]; then
  # The tarball isn't tracked; examples/build/task.py builds it on its first run.
  # Same recipe here, so a fresh checkout works without running the build.
  command -v python3 >/dev/null || { echo "setup-output.sh needs python3 to build $FIXTURE" >&2; exit 1; }
  python3 - "$FIXTURE" <<'PY'
import io
import sys
import tarfile
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
buf = io.BytesIO(b"print('orders worker 1.4.2')\n")
with tarfile.open(path, "w:gz") as tar:
    info = tarfile.TarInfo("app/worker.py")
    info.size = len(buf.getvalue())
    info.mtime = 1790640000
    tar.addfile(info, buf)
PY
fi
sudo -v   # ask for the password now, not halfway through

sudo rm -rf "$OUT"
sudo mkdir -p "$OUT"
# Same 151-byte tarball the build used.
sudo cp "$FIXTURE" "$OUT/"
# Its checksum file (83 bytes, as captured).
(cd "$OUT" && sha256sum app-1.4.2.tar.gz | sudo tee app-1.4.2.sha256 >/dev/null)
# The status-report job's file (50 bytes), text from its transcript.
printf 'orders service: ok\nversion: 2.3.1\nqueue depth: 14\n' | sudo tee "$OUT/status.txt" >/dev/null
# Timestamps from Falco/audit (UTC).
sudo touch -d '2026-09-29 14:53:32 UTC' "$OUT/status.txt"
sudo touch -d '2026-09-29 14:54:53 UTC' "$OUT/app-1.4.2.tar.gz" "$OUT/app-1.4.2.sha256" "$OUT"
sudo chown -R root:root "$OUT"
TZ=UTC ls -la "$OUT"
