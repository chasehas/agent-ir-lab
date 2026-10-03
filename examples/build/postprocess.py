"""Turn a raw examples capture into shared evidence for worked examples 2-4.

Usage (repo root, with the venv):
  python examples/build/postprocess.py <capture dir> <evidence dir> [--notes FILE]

The rules for what may be changed are in lab/evidence.py.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, so `lab` imports without PYTHONPATH
from lab.evidence import EvidenceConfig, process

CONFIG = EvidenceConfig(
    sandbox_image="lab/agent-sandbox",
    hostname="ci-runner-01",
    build_dir_suffix="/examples/build",
    job_dir="/opt/agent-jobs",
    platform_dir="/opt/agent-platform",
    mounts={"/output": "/srv/agent-output"},
    compose_vars={"${AGENT_OUTPUT_DIR:-/srv/agent-output}": "/srv/agent-output"},
    audit_keys={"agent_output"},
    service_logs={"services/orders-access.log": "services/orders-access.log"},
    listings={"host/agent-output-listing.txt": "host/agent-output-listing.txt"},
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=Path)
    ap.add_argument("evidence", type=Path)
    ap.add_argument("--notes", type=Path, help="where to write the processing notes")
    args = ap.parse_args()
    notes = process(args.capture, args.evidence, CONFIG)
    if args.notes:
        args.notes.parent.mkdir(parents=True, exist_ok=True)
        args.notes.write_text(notes)
    print(notes)


if __name__ == "__main__":
    main()
