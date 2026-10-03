"""Scan evidence for strings that shouldn't ship publicly (usernames, hostnames, local paths).

Usage: python tools/check_log_privacy.py <file or dir>... [--pattern REGEX ...]
Directories are scanned recursively. .eval files are read through Inspect (their
zip entries may be zstd-compressed); everything else is read as text.
Exits 1 if anything matches.
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

from inspect_ai.log import read_eval_log

DEFAULT_PATTERNS = [r"chase", r"AURORA", r"/mnt/c/", r"/home/(?!ci\b)\w+", r"C:\\\\Users", r"@gmail\.com", r"/root/\.claude"]
# Expected: Inspect records the git remote of the repo the run came from (this repo).
ALLOWED = ["github.com/chasehas/agent-ir-lab"]


def read_text(path: Path) -> str:
    if path.suffix == ".eval":
        with zipfile.ZipFile(path) as z:
            names = "\n".join(z.namelist())
        return names + "\n" + read_eval_log(str(path)).model_dump_json(indent=1)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--pattern", action="append", default=[])
    args = parser.parse_args()
    regex = re.compile("|".join(DEFAULT_PATTERNS + args.pattern), re.IGNORECASE)

    files = []
    for p in args.paths:
        files += sorted(f for f in p.rglob("*") if f.is_file()) if p.is_dir() else [p]

    found = False
    for path in files:
        text = read_text(path)
        for allowed in ALLOWED:
            text = text.replace(allowed, "<allowed>")
        for m in regex.finditer(text):
            found = True
            start = max(0, m.start() - 60)
            print(f"{path} :: ...{text[start : m.end() + 60]}...".replace("\n", " "))
    print(f"scanned {len(files)} files: " + ("FOUND MATCHES" if found else "clean"))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
