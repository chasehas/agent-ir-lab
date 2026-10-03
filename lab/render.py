"""Render an Inspect .eval log as a plain Markdown transcript.

For readers without Inspect View, and for quoting excerpts in the lab text.
Shows each model turn (reasoning, text, tool calls), each tool result, and,
nested under each tool call, the commands the harness actually ran in the
sandbox.

Usage:
  python -m lab.render <log.eval> [--out transcript.md] [--no-harness] [--sample N]
"""

import argparse
import json
import shlex
from datetime import datetime
from pathlib import Path

from inspect_ai.log import read_eval_log
from inspect_ai.model import ContentReasoning, ContentText

HARNESS_CMD_MAX = 160


def ts(value) -> str:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.strftime("%H:%M:%S.%f")[:-3]


def fence(text: str, lang: str = "") -> str:
    text = text.strip("\n")
    marker = "````" if "```" in text else "```"
    return f"{marker}{lang}\n{text}\n{marker}"


# Boilerplate Inspect prepends to its own probe scripts; dropped so the summary shows what the probe does.
HARNESS_PREAMBLE = (
    "inspect_image_path=${PATH-}",
    "PATH=/usr/sbin:/usr/bin:/sbin:/bin",
    "export PATH",
    "unset CDPATH",
    "set -u",
    "umask 077",
)


def script_args(cmd: str) -> list[str]:
    """The arguments after the script in `sh -c '<script>' args...`, or [] if there are none."""
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return []
    return argv[3:] if len(argv) > 3 and argv[1] == "-c" else []


def harness_cmd(cmd) -> str:
    """One-line summary of a sandbox exec command.

    Long scripts are cut short, but the arguments after an `sh -c` script are
    always kept: they say what the script acts on (for the helper install, the
    target directory and the `tar xzf -` that copies the helper in).
    """
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    raw = cmd or ""
    lines = [line.strip() for line in raw.splitlines()]
    lines = [line for line in lines if line and line not in HARNESS_PREAMBLE]
    cmd = " ; ".join(lines).replace("/bin/sh -c ' ; ", "/bin/sh -c '").replace("inspect_image_path=${PATH-} ; ", "")
    if len(cmd) <= HARNESS_CMD_MAX:
        return cmd
    args = script_args(raw)
    if args:
        tail = shlex.join(args)
        head = max(HARNESS_CMD_MAX - len(tail) - 3, 60)
        return cmd[:head] + "…' " + tail
    return cmd[: HARNESS_CMD_MAX - 1] + "…"


def render(path: Path, harness: bool = True, sample_index: int = 0) -> str:
    log = read_eval_log(str(path), resolve_attachments=True)
    sample = log.samples[sample_index]
    out: list[str] = []

    sandbox = log.eval.sandbox
    out.append(f"# Transcript: {log.eval.task} / sample {sample.id}")
    out.append("")
    out.append("| Field | Value |")
    out.append("|---|---|")
    out.append(f"| Log file | `{path.name}` |")
    out.append(f"| Task | `{log.eval.task}` |")
    out.append(f"| Model | `{log.eval.model}` |")
    out.append(f"| Run created (UTC) | {log.eval.created} |")
    out.append(f"| Sandbox | `{sandbox.type if sandbox else 'none'}`" + (f" (`{sandbox.config}`)" if sandbox and sandbox.config else "") + " |")
    out.append(f"| Harness | inspect_ai {log.eval.packages.get('inspect_ai', '?')} |")
    out.append(f"| Status | {log.status} |")
    out.append("")
    out.append("All times are UTC, from the log's event timestamps.")
    out.append("")

    for message in sample.messages:
        if message.role == "system":
            out.append("## System prompt (set by the harness)")
            out.append("")
            out.append(fence(message.text))
            out.append("")
        elif message.role == "user":
            out.append("## Task (user message)")
            out.append("")
            out.append(fence(message.text))
            out.append("")
            break

    out.append("## Events")
    out.append("")

    events = list(sample.events)
    turn = 0
    for i, event in enumerate(events):
        kind = event.event
        if kind == "sample_init":
            files = []
            for e in sample.events:
                if e.event == "sandbox" and e.action == "write_file":
                    files.append(e.file)
            out.append(f"**{ts(event.timestamp)} — setup.** The harness starts the sandbox" + (f" and copies in: {', '.join(f'`{f}`' for f in files)}." if files else "."))
            out.append("")
        elif kind == "model":
            turn += 1
            msg = event.output.message
            out.append(f"### {ts(event.timestamp)} — model turn {turn}")
            out.append("")
            content = msg.content if isinstance(msg.content, list) else [ContentText(text=msg.content)] if msg.content else []
            for part in content:
                if isinstance(part, ContentReasoning):
                    label = "Reasoning (redacted)" if part.redacted else "Reasoning"
                    out.append(f"*{label}:*")
                    out.append("")
                    out.append("> " + part.reasoning.replace("\n", "\n> "))
                    out.append("")
                elif isinstance(part, ContentText) and part.text.strip():
                    out.append("*Text:*")
                    out.append("")
                    out.append("> " + part.text.replace("\n", "\n> "))
                    out.append("")
            for call in msg.tool_calls or []:
                out.append(f"*Tool call* `{call.id}`: **{call.function}**")
                out.append("")
                out.append(fence(json.dumps(call.arguments, indent=2), "json"))
                out.append("")
        elif kind == "tool":
            status = f" — error: `{event.error.type}`" if event.error else ""
            out.append(f"**{ts(event.timestamp)} — tool runs** `{event.id}` ({event.function}){status}")
            out.append("")
            if harness:
                # Sandbox execs between this tool event and the next model/tool event
                # are what the harness actually ran to carry out the call.
                execs = []
                for later in events[i + 1 :]:
                    if later.event in ("model", "tool"):
                        break
                    if later.event == "sandbox":
                        execs.append(later)
                if execs:
                    out.append("What the harness did in the sandbox:")
                    out.append("")
                    for e in execs:
                        if e.action == "exec":
                            out.append(f"- {ts(e.timestamp)} exec `{harness_cmd(e.cmd)}`")
                        else:
                            out.append(f"- {ts(e.timestamp)} {e.action.replace('_', ' ')} `{e.file}`")
                    out.append("")
            result = event.result if isinstance(event.result, str) else json.dumps(event.result, default=str)
            out.append("Result returned to the model:")
            out.append("")
            out.append(fence(result or "(empty)"))
            out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-harness", action="store_true", help="omit the sandbox exec lines")
    parser.add_argument("--sample", type=int, default=0)
    args = parser.parse_args()
    text = render(args.log, harness=not args.no_harness, sample_index=args.sample)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
