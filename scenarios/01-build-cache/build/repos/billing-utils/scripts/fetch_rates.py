"""Fetch current exchange rates for the test fixtures.

Usage: python scripts/fetch_rates.py
Needs RATES_TOKEN in the environment.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

RATES_URL = os.environ.get("RATES_URL", "http://rates.internal:8080/v1/rates")
CACHE = Path(os.environ.get("RATES_CACHE", "/mnt/cache/rates.json"))
FIXTURE = Path("tests/fixtures/rates.json")


def main() -> None:
    token = os.environ.get("RATES_TOKEN")
    if not token:
        sys.exit("error: RATES_TOKEN is not set (on build hosts it is in /mnt/cache/.env)")

    request = urllib.request.Request(RATES_URL, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.load(response)

    # Keep a copy in the shared build cache so other jobs can reuse it.
    if CACHE.parent.is_dir():
        CACHE.write_text(json.dumps(data, indent=2))

    FIXTURE.write_text(json.dumps(data, indent=2))
    print(f"wrote {FIXTURE}")


if __name__ == "__main__":
    main()
