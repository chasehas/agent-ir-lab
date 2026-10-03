# Worked example 1: Anatomy of a transcript

**Time:** about 20 minutes. **You need:** a text editor. Inspect View is optional.

An agent transcript is the record an agent platform keeps of a run: what the agent was told, what it thought, what it asked to do, and what came back. This example walks through one ordinary run, where nothing goes wrong, and names each part. The later examples use these names.

## The run

A coding agent was asked to fix failing unit tests in a tiny Python project. It ran inside a Docker container with no network and no host mounts. It ran the tests, read the source, made a one-line fix, re-ran the tests, and reported back. Total time: about 9 seconds.

This is a scripted run. The "model" is a fixed script (Inspect's `mockllm`), but every tool call really ran in a real container, and every result is real output. That's why the model field says `mockllm/model`. In a real run it names the model and provider, for example `anthropic/claude-...` or `ollama/qwen3:8b`. Real models also take seconds to minutes per turn; here the gaps between turns are only the container's time.

## Open it

Open two files side by side in your editor:

- **[evidence/raw-log.json](evidence/raw-log.json)**, the raw log. This is what you'd actually be handed.
- **[transcript.md](transcript.md)**, the same log rendered as readable text, with labels. Use it to find your place, then check the raw log to see what's really recorded.

The raw log is long (about 3,300 lines) because every part appears more than once: once in the message history and again in the event stream. The event stream is the part that matters most for an investigation, because it has the timestamps. Here's where each part lives:

| Part (see table below) | Where it is in `raw-log.json` |
|---|---|
| Run header | `eval` at the top: `task`, `model`, `created`, `sandbox`, `revision`, `packages` |
| System prompt and task | `samples[0].messages[0]` (role `system`) and `[1]` (role `user`) |
| Model turn | `samples[0].events[]` entries with `"event": "model"`. What the model said is in `output.choices[0].message`: `content`, plus `tool_calls`. `content` is usually a list of `reasoning` and `text` blocks, but a plain string when there's only text (turn 5 here) |
| Tool call and result | Entries with `"event": "tool"`: `function`, `arguments`, `result` |
| Harness record | Entries with `"event": "sandbox"`: `action`, `cmd`, `output` |
| Timestamps | `timestamp` on every event, in UTC |
| Final answer | The last `"event": "tool"` with `"function": "submit"`, and `samples[0].output` |

Search the raw file for `"event": "model"`, `"event": "tool"`, and `"event": "sandbox"` to step through it.

Two other ways in, if you want them:

- **Inspect View,** the viewer agent teams actually use. `pip install inspect-ai==0.3.272`, then `inspect view --log-dir examples/01-anatomy/evidence`, and open http://127.0.0.1:7575. It hides the harness record by default: on the Transcript tab, open **Events** and tick **Sandbox**.
- **The original file.** [`evidence/*.eval`](evidence/) is what Inspect writes: a zip of JSON files (`header.json`, `samples/<id>.json`, ...). The entries are zstd-compressed, so plain `unzip` may list them but fail to extract. `raw-log.json` was made from it with `inspect log dump --resolve-attachments full`. Without that flag, repeated text shows up as `attachment://<hash>` placeholders.

## The parts

| Part | What it tells you | Closest thing you already know |
|---|---|---|
| **Run header** | Task name, model, start time, sandbox type and config file, harness version, even the git commit of the code that launched the run | Case metadata; the parent process and its config |
| **System prompt** | Standing instructions from the harness, not the user. Here it's Inspect's default agent prompt | The policy or config a service runs under |
| **Task** (user message) | What the agent was asked to do | The ticket, or the command line that started the job |
| **Model turn** | One response from the model. Can hold three things: **reasoning** (its working notes), **text** (what it says), and **tool calls** (requests to act) | The analyst's notes plus the command they typed |
| **Tool call** | The function name and arguments the model asked for, with an ID like `call_01` | A line of shell history |
| **Tool result** | What the harness returned to the model after running the call | The command's output on screen |
| **Harness record** | What the platform actually executed in the sandbox to carry out each call (Inspect calls these "sandbox events") | Process accounting or `auditd`, but written by the harness, not the OS |
| **Timestamps** | Every event has one, in UTC | Log timestamps |
| **Final answer** | The agent's own summary, sent with the `submit` tool | The engineer's closing note on the ticket |

## Six things to notice

**1. The tool call is not the process.** The agent asked for `bash` with `ls -la && python -m unittest -v`. The harness record says it ran `bash --login -c 'ls -la && python -m unittest -v'` inside the container, through `docker exec`. On the host it was wrapped once more: Inspect puts `/usr/bin/timeout -k 5s 60s` in front of any command that has a time limit, and the harness record leaves that out. Example 2's host logs show the wrapper. When you look for a tool call in host logs, search for the wrapper, not just the command.

**2. One tool call can start many processes.** For the agent's first `text_editor` call (11:36:34), the harness record shows 11 commands in the container. Only the last one read the file. Before that, the harness checked the OS and CPU (`uname`), read `/etc/os-release`, read its own privileges from `/proc/self/status`, created a hidden directory under `/var/tmp`, unpacked a helper binary into it, and started the helper (`/var/tmp/.da7be258e003d428/inspect-sandbox-tools`). In host logs, all of that looks like activity in the agent's container. None of it was the agent's choice. Know what your harness does on its own before you call something suspicious.

**3. The harness record can be incomplete too.** It shows the helper being copied in, at 11:36:37.116: a directory check that ends with `tar xzf -`, unpacking an archive sent on standard input. It doesn't show what was in the archive. Nor does it list every command: in example 2, that run's first `text_editor` call has 11 commands in the harness record and 14 in Docker's event log. The harness record covers what the harness chose to log.

**4. Output order is not execution order.** `ls -la` ran before the tests. But in the first tool result, the test output comes first and the directory listing comes last. The bash tool returns the error stream (where Python's `unittest` writes) ahead of normal output. Don't build a timeline from the order of lines inside one tool result.

**5. Reasoning is the model's account, not a record.** In turn 2, the reasoning predicts the bug before the agent has read the code. Here it happens to be right. In real runs, reasoning may be summarized by the provider, missing entirely, or simply wrong. Treat it like a witness statement: useful, and checked against the evidence.

**6. The final answer is a claim.** The agent says it fixed `word_count` and didn't change the tests. You can check both from the transcript: the `str_replace` result shows the one-line change to `textstats.py`, and the last test run shows 4 passed. Here the claim holds. In scenario 01, the final answer is accurate but leaves things out.

One more detail worth a look: `unzip -l` on the `.eval` file shows its entries at **07:36**, while every event inside says **11:36**. Zip files store local time with no timezone; the build machine was on US Eastern. Same run, two clocks.

## Try it

<details><summary>1. How many tool calls did the agent make? How many commands does the harness record show it running in the container?</summary>

Five tool calls (`call_01` to `call_05`, the last one being `submit`). The harness record shows 14 commands: 2 carried out the agent's bash calls, 2 carried out its `text_editor` view and edit, and 10 were the harness setting up its `text_editor` helper. `submit` runs nothing in the container. Before the agent started, the record also shows two `write_file` events (11:36:31–32) copying the project in. Example 2 shows that the record can miss commands, so the real count may be higher.
</details>

<details><summary>2. When was textstats.py changed, and by which call?</summary>

`call_03`, the `text_editor` `str_replace`. The tool call went out at 11:36:39.626 UTC; the harness ran the edit at 11:36:40.296.
</details>

<details><summary>3. If you had the host's audit log, what process would you look for to match call_04?</summary>

A `docker exec` into the container at about 11:36:40.97 UTC, running `/usr/bin/timeout -k 5s 60s bash --login -c 'python -m unittest -v'`. Under `timeout`, look for `bash`, then `python` with the same process ID: when the last thing in a `bash -c` string is a single program, bash replaces itself with it. Worked example 2 makes this kind of match for another run, with real host logs.
</details>

<details><summary>4. What in the transcript supports the reasoning in turn 2?</summary>

The `view` result in turn 2 shows line 6, `return len(text.split(" "))`, and the test failures in turn 1 (`1 != 0` for the empty string, `5 != 4` for extra whitespace) are what splitting on a single space would produce. The final test run passing after the one-line fix confirms it.
</details>

<details><summary>5. What can't you verify from the transcript alone?</summary>

Anything the harness didn't log. Whether any other process ran in the container. Whether the container really had no network or mounts; the header only names the config file, `compose.yaml`, not its contents. Whether the file on disk after the run matches what the tool result shows. For those you need the platform and host evidence.
</details>

## Where this fits

In the [playbook](https://docs.google.com/document/d/1qjdoAezkKrh4rZQlfZlpmzMFknomJhLCTR3UJ-Pg2BQ/edit), this is groundwork for Q3 (agent log analysis). Next: worked example 2 matches tool calls like these to host logs.

## How this was made

[`build/`](build/) holds the scripted agent (`task.py`), the project it fixed, and the sandbox config. To regenerate, from the repo root on Linux or WSL: `inspect eval examples/01-anatomy/build/task.py --log-dir examples/01-anatomy/build/logs`. Timestamps will differ. The helper directory name won't: it's fixed for each Inspect version.
