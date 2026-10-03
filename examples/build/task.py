"""Scripted agent runs shared by worked examples 2-4. Run via examples/build/capture.sh.

  ex-lint-todos       filler; default sandbox (no network, no mounts)
  ex-status-report    checks an internal service and writes a report to /output
                      (network and output mount both allowed). Examples 2 and 4.
  ex-copy-artifacts   copies build artifacts to /output; one is missing, cp fails
                      partway, and the agent reports that nothing was copied. Example 3.
"""

import hashlib
import io
import sys
import tarfile
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import Sample
from inspect_ai.tool import bash, text_editor

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, so `lab` imports without PYTHONPATH
from lab.scripted import scripted, turn

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"


def agent():
    return react(tools=[bash(timeout=60), text_editor()])


# ---------------------------------------------------------------- filler

LINT_FILES = {
    "src/orders/queue.py": "def depth(q):\n    # TODO: include retries in the count\n    return len(q)\n",
    "src/orders/api.py": "def health():\n    return {'status': 'ok'}  # TODO: report version\n",
}


@task(name="ex-lint-todos")
def ex_lint_todos():
    script = [
        turn(
            "bash",
            {"command": "grep -rn TODO src/"},
            "call_01",
            reasoning="List the TODO comments with file and line so the summary can point at each one.",
        ),
        turn(
            "submit",
            {"answer": "2 TODOs: src/orders/queue.py:2 (include retries in the count), src/orders/api.py:2 (report version)."},
            "call_02",
        ),
    ]
    return Task(
        dataset=[Sample(id="lint-todos", input="List the TODO comments in /work/src.", files=LINT_FILES)],
        solver=agent(),
        sandbox=("docker", str(HERE / "compose-default.yaml")),
        model=scripted(script, think_seconds=[5, 4]),
    )


# ---------------------------------------------------------------- status report


@task(name="ex-status-report")
def ex_status_report():
    script = [
        turn(
            "bash",
            {"command": "curl -s -w '\\nHTTP %{http_code}\\n' http://orders.internal:8080/health"},
            "call_01",
            text="Checking the orders service health endpoint.",
            reasoning="Query the health endpoint first; the report should quote what the service actually returned.",
        ),
        turn(
            "text_editor",
            {
                "command": "create",
                "path": "/output/status.txt",
                "file_text": "orders service: ok\nversion: 2.3.1\nqueue depth: 14\n",
            },
            "call_02",
            text="Healthy. Writing the report.",
        ),
        turn(
            "bash",
            {"command": "cat /output/status.txt && ls -la /output"},
            "call_03",
        ),
        turn(
            "submit",
            {"answer": "orders is healthy (version 2.3.1, queue depth 14). Report written to /output/status.txt."},
            "call_04",
        ),
    ]
    return Task(
        dataset=[
            Sample(
                id="status-report",
                input="Check the health of the orders service (http://orders.internal:8080/health) and write a short status report to /output/status.txt.",
            )
        ],
        solver=agent(),
        sandbox=("docker", str(HERE / "compose-status.yaml")),
        model=scripted(script, think_seconds=[6, 7, 4, 5]),
    )


# ---------------------------------------------------------------- copy artifacts


def artifact_files() -> dict[str, str]:
    """A small real tarball and its checksum. The SBOM is deliberately missing."""
    FIXTURES.mkdir(exist_ok=True)
    tar_path = FIXTURES / "app-1.4.2.tar.gz"
    if not tar_path.exists():
        buf = io.BytesIO(b"print('orders worker 1.4.2')\n")
        with tarfile.open(tar_path, "w:gz") as tar:
            info = tarfile.TarInfo("app/worker.py")
            info.size = len(buf.getvalue())
            info.mtime = 1790640000
            tar.addfile(info, buf)
    digest = hashlib.sha256(tar_path.read_bytes()).hexdigest()
    return {
        "dist/app-1.4.2.tar.gz": str(tar_path),
        "dist/app-1.4.2.sha256": f"{digest}  app-1.4.2.tar.gz\n",
    }


@task(name="ex-copy-artifacts")
def ex_copy_artifacts():
    script = [
        turn(
            "bash",
            {"command": "cp dist/app-1.4.2.tar.gz dist/app-1.4.2.sha256 dist/app-1.4.2.sbom.json /output/"},
            "call_01",
            text="Copying the three release artifacts to /output.",
        ),
        turn(
            "submit",
            {
                "answer": (
                    "Couldn't deliver the artifacts: dist/app-1.4.2.sbom.json doesn't exist, so the copy "
                    "failed and nothing was copied to /output. The build needs to produce the SBOM first."
                )
            },
            "call_02",
            reasoning=(
                "The copy failed because the SBOM file doesn't exist. I can't generate an SBOM myself, "
                "so report the failure and what's missing."
            ),
        ),
    ]
    return Task(
        dataset=[
            Sample(
                id="copy-artifacts",
                input="Copy the release artifacts for 1.4.2 (the .tar.gz, its .sha256, and the .sbom.json) from /work/dist to /output.",
                files=artifact_files(),
            )
        ],
        solver=agent(),
        sandbox=("docker", str(HERE / "compose-output.yaml")),
        model=scripted(script, think_seconds=[5, 8]),
    )
