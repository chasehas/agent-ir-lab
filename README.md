# Agent IR Lab

**Status: draft v0.1, October 2026.** Built for the M3 fellowship. Not yet tested by human incident responders. Found a mistake or have feedback? Open an issue.

Hands-on material for incident responders meeting AI agent transcripts for the first time.

**[Try the demo in your browser](https://chasehas.github.io/agent-ir-lab/)**: the demo-day walkthrough, from SOC ticket to transcript to Falco alerts, with nothing to install.

The takeaway: an agent's transcript records what the agent saw and claimed, so check it against host evidence before you act on it. In the demo, the agent says nothing was copied, and the host shows two files waiting to ship.

You already know how to read Linux host evidence: audit logs, process trees, network logs, file timelines. When an AI agent is involved, there's a new source: the **transcript**, the agent platform's record of what the agent was told, what it thought, what it asked to do, and what came back. This lab shows you what a transcript contains, how it lines up with the host evidence you know, where it can mislead you, and how to use both together in an investigation.

It's the practical companion to the [Agent Incident Response Playbook](https://docs.google.com/document/d/1qjdoAezkKrh4rZQlfZlpmzMFknomJhLCTR3UJ-Pg2BQ/edit).

## Start here

Work through these in order. Each one takes 20–90 minutes.

| | What you'll do |
|---|---|
| [Worked example 1: Anatomy of a transcript](examples/01-anatomy/) | Read one ordinary agent run and name every part of the transcript |
| [Worked example 2: Matching the transcript to the host](examples/02-join/) | Line each tool call up with what the platform, the host, and the network recorded |
| [Worked example 3: When the transcript and the host disagree](examples/03-transcript-vs-reality/) | See an agent report "nothing was copied" when two files were |
| [Worked example 4: Starting from the alert](examples/04-start-from-the-alert/) | Work backwards from a Falco alert to the run and tool call behind it |
| [Scenario 01: Build cache](scenarios/01-build-cache/) | A guided investigation, end to end: an agent in a "sandboxed" container reaches a secret and an internal service |

## What you need

- **A text editor.** Everything can be read as text. Each transcript also comes as a readable `.json` file, and worked examples 1–3 each include a Markdown rendering of their run.
- **Optional: `jq`** for filtering the JSON-lines logs (`winget install jqlang.jq`, `brew install jq`, or your package manager).
- **Optional: Inspect View**, the transcript viewer agent teams actually use. Needs Python 3.10 or later:

  ```bash
  pip install inspect-ai==0.3.272
  inspect view --log-dir examples/01-anatomy/evidence
  ```

  Then open http://127.0.0.1:7575. Point `--log-dir` at any `evidence/` or `evidence/transcripts/` folder.

You don't need Docker, a model, or an API key to work the material.

## How the evidence was made

Every agent run here is **scripted**: instead of a live model, a fixed script of tool calls drives the agent, using [Inspect](https://inspect.aisi.org.uk/)'s mock model. That keeps the runs repeatable. But everything else is real. The tool calls ran in real Docker containers, and the host evidence was recorded while they ran: the Linux audit log (`auditd`), [Falco](https://falco.org/) alerts, [Zeek](https://zeek.org/) network logs, Docker's event stream, and the services' own logs.

The raw captures were then cleaned up: the lab's own tooling was removed, and build-machine paths were swapped for the story's. Each scenario's answer key lists every change. Nothing the agent did or the collectors saw was edited. The transcripts' model field reads `mockllm/model` because of the scripting.

Each example and scenario has a `build/` folder with everything used to make it. You can regenerate the evidence on a Linux machine with Docker. Set up a Python environment with `tools/wsl-setup.sh`, then run the folder's `capture.sh` and `postprocess.py`; each script's header gives its usage. Worked example 1 needs only `inspect eval`; see its README.

## What's here

| Folder | What it is |
|---|---|
| `examples/` | Worked examples 1–4 |
| `scenarios/` | Full investigations, each with a briefing, evidence, guided questions, and an answer key |
| `lab/`, `tools/` | The scripts that build and check the evidence |
| `demo/` | Props from the M3 demo day: a mock SOC queue, a Falco console, and a live-response terminal, built from the examples' evidence |

## What's next

Planned: a harder scenario with genuinely unclear intent, confusing guidance, and decisions to make under uncertainty; a playground for running your own local agent and reading its transcripts; more worked examples (summarized and missing reasoning, context compaction, emergency stop).

## License

MIT. See [LICENSE](LICENSE).
