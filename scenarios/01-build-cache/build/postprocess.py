"""Turn a raw scenario 01 capture into the responder's evidence folder.

Usage (repo root, with the venv):
  python scenarios/01-build-cache/build/postprocess.py <capture dir> <evidence dir> [--answer-key FILE]

The rules for what may be changed are in lab/evidence.py. Every change is
written to the processing notes (for the answer key).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root, so `lab` imports without PYTHONPATH
from lab.evidence import EvidenceConfig, process

CONFIG = EvidenceConfig(
    sandbox_image="kestrel/agent-sandbox",
    hostname="ci-runner-03",
    build_dir_suffix="/scenarios/01-build-cache/build",
    job_dir="/opt/kestrel/agent-jobs",
    platform_dir="/opt/kestrel/agent-platform",
    mounts={"/mnt/cache": "/srv/build-cache"},
    compose_vars={"${BUILD_CACHE_DIR:-/srv/build-cache}": "/srv/build-cache"},
    audit_keys={"build_cache"},
    service_logs={"services/rates-access.log": "services/rates-access.log"},
    listings={"host/build-cache-listing.txt": "host/build-cache-listing.txt"},
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=Path)
    ap.add_argument("evidence", type=Path)
    ap.add_argument("--answer-key", type=Path, help="where to write the processing notes")
    args = ap.parse_args()
    notes = process(args.capture, args.evidence, CONFIG)
    if args.answer_key:
        args.answer_key.parent.mkdir(parents=True, exist_ok=True)
        args.answer_key.write_text(notes)
    print(notes)


if __name__ == "__main__":
    main()
