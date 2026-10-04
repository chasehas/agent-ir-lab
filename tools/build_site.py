"""Build the static demo site for GitHub Pages.

Copies the demo pages into an output folder, points the ticket page's
Inspect button at a bundled copy of Inspect View, and adds a banner to
each tool page.

    pip install inspect-ai==0.3.272
    python tools/build_site.py            # writes site/
    python -m http.server -d site 8000    # then open http://127.0.0.1:8000
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "demo"
TRANSCRIPTS = REPO / "examples" / "evidence" / "transcripts"
PAGES = ["ticket.html", "falco.html", "terminal.html"]

LOCAL_INSPECT = 'const INSPECT_URL = "http://127.0.0.1:7575/";'
SITE_INSPECT = 'const INSPECT_URL = "inspect/";'

BANNER = (
    '<div style="background:#fef3c7;color:#713f12;border-bottom:1px solid #fcd34d;'
    'padding:6px 24px;font:15px/1.4 \'Segoe UI\',system-ui,-apple-system,Roboto,Arial,sans-serif;">'
    "Demo prop: fictional company, real evidence. "
    '<a href="index.html" style="color:#713f12;font-weight:600;">About this demo &rarr;</a>'
    "</div>"
)


def replace_once(text: str, old: str, new: str, name: str) -> str:
    if text.count(old) != 1:
        sys.exit(f"{name}: expected exactly one {old!r}")
    return text.replace(old, new)


def build(out: Path, inspect_cmd: str) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for name in PAGES:
        html = (DEMO / name).read_text(encoding="utf-8")
        html = replace_once(html, "<body>", "<body>\n" + BANNER, name)
        if name == "ticket.html":
            html = replace_once(html, LOCAL_INSPECT, SITE_INSPECT, name)
        (out / name).write_text(html, encoding="utf-8", newline="\n")

    shutil.copyfile(DEMO / "index.html", out / "index.html")

    # Bundle only the .eval logs; the .json copies would list each run twice.
    with tempfile.TemporaryDirectory() as tmp:
        for log in sorted(TRANSCRIPTS.glob("*.eval")):
            shutil.copyfile(log, Path(tmp) / log.name)
        subprocess.run(
            [inspect_cmd, "view", "bundle", "--log-dir", tmp,
             "--output-dir", str(out / "inspect"), "--overwrite"],
            check=True,
        )

    # The bundle records the absolute path of the temp log dir; don't publish it.
    index = out / "inspect" / "index.html"
    html = index.read_text(encoding="utf-8")
    html = re.sub(r'"abs_log_dir":\s*"[^"]*"', '"abs_log_dir": "logs"', html)
    index.write_text(html, encoding="utf-8", newline="\n")

    print(f"Site written to {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=REPO / "site")
    parser.add_argument("--inspect", default="inspect", help="path to the inspect CLI")
    args = parser.parse_args()
    build(args.out.resolve(), args.inspect)
