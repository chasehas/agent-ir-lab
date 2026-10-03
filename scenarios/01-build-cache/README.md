# Scenario 01: Build cache

**Time:** 60–90 minutes. **You need:** a text editor. `jq` helps. Inspect View is optional.

A coding agent was fixing a failing test in a container that was supposed to be isolated. A Falco alert says the container made a network connection. Your job: find out what happened, what left the sandbox, and what to do now, using the agent's transcript alongside ordinary host and network evidence.

This is the guided scenario. It has no traps. The questions walk you through it, and every answer is in the evidence. If you haven't done the [worked examples](../../examples/), start with [example 1](../../examples/01-anatomy/) so the parts of a transcript are familiar.

## How to work it

1. Read the [briefing](BRIEFING.md). That's what the SOC handed you.
2. Answer the [guided questions](QUESTIONS.md) using the files in [`evidence/`](evidence/).
3. Check yourself against the [answer key](answer-key/ANSWERS.md). Don't open `answer-key/` until you're done; it also contains the true timeline.

## Opening the evidence

| Files | How to read them |
|---|---|
| `transcripts/*.json` | Any editor. Search for `"event": "tool"` to step through the tool calls. See [example 1](../../examples/01-anatomy/README.md#open-it) for a map of the file |
| `transcripts/*.eval` | `inspect view --log-dir evidence/transcripts` (after `pip install inspect-ai==0.3.272`). Tick **Sandbox** under **Events** to see the harness's commands |
| `platform/docker-events.jsonl`, `host/falco.jsonl`, `network/*.log` | One JSON object per line. `jq -c 'select(...)'` or any editor |
| `platform/docker-inspect-*.json` | JSON. Look at `Mounts`, `NetworkSettings.Networks`, and `Config.Labels` |
| `host/audit.log` | Raw Linux audit records. Several lines share one event ID in `msg=audit(<time>:<id>)`. Use `host/audit-interpreted.txt` (the `ausearch -i` version) to read it without Linux tools |
| `services/rates-access.log` | Apache-style access log |

## Timestamps

Every source writes time its own way. Put everything in UTC before you build a timeline. Here is the same instant, 13:03:21.644 UTC, in each format:

| Source | Format | The same instant |
|---|---|---|
| Transcripts | ISO 8601, UTC | `2026-09-29T13:03:21.644+00:00` |
| Falco | ISO 8601, UTC | `2026-09-29T13:03:21.644Z` |
| `docker events` | Unix epoch in `time` (seconds) and `timeNano` (nanoseconds) | `1790687001`, `1790687001644…` |
| Zeek | Unix epoch with decimals in `ts` | `1790687001.644` |
| `audit.log` | Unix epoch inside `msg=audit(<time>:<event id>)`. `audit-interpreted.txt` was made with `TZ=UTC`, so its times are UTC. (`ausearch -i` normally prints the local time of whatever machine runs it, which is a trap of its own) | `msg=audit(1790687001.644:<id>)` |
| Rates service | Local time with offset | `[29/Sep/2026:09:03:21 -0400]` |

To convert an epoch: `date -u -d @1790687001` (Linux), or `[DateTimeOffset]::FromUnixTimeSeconds(1790687001).UtcDateTime` (PowerShell).

Audit timestamps move in steps of about 4 ms, so don't try to order audit events against Falco or Zeek more finely than about 10 ms.

## Things that trip people up

- **In `audit.log`, trust `EXECVE` and the `SYSCALL` fields over `PROCTITLE`.** The `PROCTITLE` line can show a parent's command line. Here, the records for the `.env` read and the `rates.json` write show the harness's `timeout ...` command line, though the process doing the work was bash, then python. Go by `pid`, `comm`, and `exe`.
- **Shells replace themselves.** When the last command in a `bash -c` string is a single program, bash runs it in its own place: same process ID, new program. That's why Falco can list `python`'s parent as `timeout`, not `bash`.
- **Container paths aren't host paths.** Falco and the audit log show the path the process inside the container used, like `/mnt/cache/...`. `docker inspect` (`Mounts`) tells you which host folder that is.

## About this scenario

The agent runs were scripted, but everything in `evidence/` was recorded from real runs: the containers, network traffic, and host activity really happened. [answer-key/processing.md](answer-key/processing.md) lists every change made to the raw capture (removing the lab's own tooling, swapping build-machine paths for the story's). Nothing the agent did or the collectors saw was edited.

A few places where the lab's scaffolding shows. None of them are leads:

- The transcripts' model field reads `mockllm/model`, because the runs were scripted.
- The transcript headers point to this repo and to `build/task.py`, where the scripted runs live. That's the answer key in another form; don't open it.
- The build-cache folder, its `.env`, and `pip/` were created just before the runs, so their timestamps are from that morning. A real shared cache would be older.
