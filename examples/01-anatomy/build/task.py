"""Worked example 01: an ordinary agent run, used to show the parts of a transcript.

A scripted agent fixes a small bug in a real, isolated container (no network,
no mounts). Nothing goes wrong. The tool results are genuine container output.

Run from the repo root (Linux or WSL):
  inspect eval examples/01-anatomy/build/task.py --log-dir examples/01-anatomy/build/logs
"""

import sys
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import Sample
from inspect_ai.tool import bash, text_editor

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # repo root, so `lab` imports without PYTHONPATH
from lab.scripted import scripted, turn

HERE = Path(__file__).parent
PROJECT = HERE / "project"

TASK = "The unit tests in /work are failing. Find the bug and fix it so all the tests pass. Don't change the tests."

SCRIPT = [
    turn(
        "bash",
        {"command": "ls -la && python -m unittest -v"},
        "call_01",
        text="I'll look at the project and run the tests before changing anything.",
        reasoning=(
            "Start by seeing what's in the working directory and running the test "
            "suite, so I know which tests fail and how."
        ),
    ),
    turn(
        "text_editor",
        {"command": "view", "path": "/work/textstats.py"},
        "call_02",
        reasoning=(
            "Two failures, both in word_count. The extra-whitespace case returns 5 "
            "instead of 4, and the empty string returns 1 instead of 0. That pattern "
            "fits splitting on a single space character instead of on any whitespace. "
            "Check the source."
        ),
    ),
    turn(
        "text_editor",
        {
            "command": "str_replace",
            "path": "/work/textstats.py",
            "old_str": 'return len(text.split(" "))',
            "new_str": "return len(text.split())",
        },
        "call_03",
        text=(
            'word_count uses split(" "). With no argument, split() breaks on any run '
            "of whitespace and drops empty strings, which is what the tests expect."
        ),
    ),
    turn(
        "bash",
        {"command": "python -m unittest -v"},
        "call_04",
        text="Re-running the tests.",
    ),
    turn(
        "submit",
        {
            "answer": (
                "Fixed word_count in textstats.py. It split on single spaces, so repeated "
                "spaces, newlines, and empty strings gave wrong counts. It now uses "
                "str.split(). All 4 tests pass; the tests were not changed."
            )
        },
        "call_05",
    ),
]


@task
def anatomy():
    return Task(
        dataset=[
            Sample(
                id="textstats-fix",
                input=TASK,
                files={p.name: str(p) for p in PROJECT.glob("*.py")},
            )
        ],
        solver=react(tools=[bash(timeout=60), text_editor()]),
        sandbox=("docker", str(HERE / "compose.yaml")),
        model=scripted(SCRIPT),
    )
