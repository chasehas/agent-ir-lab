# Worked example 2: Matching the transcript to the host

**Time:** about 30 minutes. **You need:** a text editor. `jq` helps.

Example 1 named the parts of a transcript. This one lines each tool call up with what the platform and the host recorded. That match is the core skill for everything that follows: this tool call should be that process, this file write should be that file event, this command should be that connection.

## The run

An agent was asked to check an internal service's health and write a short status report to a shared output folder. The job is allowed to do both: its container is on the internal network and has the output folder mounted from the host. Nothing goes wrong, which makes it a clean case for learning what normal looks like on each side.

All the evidence for examples 2–4 is in [`../evidence/`](../evidence/). This example uses only the `ex-status-report` run. How the raw capture was cleaned up is in [`../build/processing.md`](../build/processing.md).

## Open it

Side by side:

- The transcript: `../evidence/transcripts/*ex-status-report*.json`, and its rendering, [transcript.md](transcript.md).
- The host's view: `../evidence/host/audit-interpreted.txt` (the `ausearch -i` version of `audit.log`; times are UTC).

Keep these nearby: `../evidence/platform/docker-events.jsonl`, `../evidence/host/falco.jsonl`, `../evidence/network/conn.log` and `http.log`, `../evidence/services/orders-access.log`.

## The match

Four layers, one row per tool call. Times are UTC.

| Tool call (transcript) | What the platform ran (`docker events`) | What the host saw (`audit.log`) | What happened outside (Falco, Zeek, service) |
|---|---|---|---|
| `call_01` at 14:53:21.174<br>bash: `curl -s ... http://orders.internal:8080/health` | 14:53:21.261: one `exec_create` of `/usr/bin/timeout -k 5s 60s bash --login -c curl ...` | 14:53:21.318 `timeout` (event 3901), 14:53:21.322 `bash` (3906), 14:53:21.326 `curl` (3909). `bash` and `curl` share PID 11904 | 14:53:21.342: Falco "Outbound connection from agent sandbox", process `curl`. Zeek: one connection, `GET /health` → 200. The service's log: `10:53:21 -0400` |
| `call_02` at 14:53:28.360<br>text_editor: create `/output/status.txt` | 14 `exec_create`s, 14:53:28.426–31.790: the harness's probes, then its helper `/var/tmp/.da7be258e003d428/inspect-sandbox-tools`. The transcript's harness record lists only 11 | The probes and the helper start. 14:53:32.290: a write to `/output/status.txt` by `inspect-sandbox` (event 4246, key `agent_output`) | 14:53:32.294: Falco "Write to host-mounted path", process `inspect-sandbox`. Also six stock Critical "Drop and execute new binary" alerts for the helper, 14:53:30–31 |
| `call_03` at 14:53:36.376<br>bash: `cat /output/status.txt && ls -la /output` | 14:53:36.437: one `exec_create` | `timeout`, `bash`, `cat`, `ls` | Nothing |
| `call_04` at 14:53:41.517<br>submit | Nothing | Nothing | Nothing |

## Things to notice

**1. The command text is the join key.** Nothing in the transcript names the container or a process ID. What carries across is the command: the transcript's `command` argument appears word for word at the end of the `exec_create` in `docker events`, and again as the `bash -c` argument in the audit log's `EXECVE` record.

**2. Each layer has its own clock format, and the order is always the same.** The transcript and Falco use ISO 8601 in UTC. `docker events` and Zeek use Unix epoch. `audit.log` uses epoch inside `msg=audit(...)`. The service logs local time with an offset. Convert everything to UTC first. Within one tool call the order doesn't change: the transcript's timestamp (the harness starts the call), then `exec_create`, then the processes, then the network or file activity. For `call_01`, the whole chain took 168 milliseconds.

**3. The process tree proves where a process ran.** Follow `curl`'s parent process IDs in the audit log: `curl` → `timeout` → `runc` → `containerd-shim-runc-v2 ... -id 57e6f530a89c...`. That ID is the container Falco named. The shim's `-id` argument is how a host process gets tied to a container.

**4. Shells replace themselves.** `bash` started as PID 11904, and 4 ms later the same PID 11904 became `curl`. When the last command in a `bash -c` string is a single program, bash runs it in its own place. That's why Falco lists `curl`'s parent as `timeout`, not `bash`.

**5. The file was written by the harness, not by a shell.** The agent asked `text_editor` to create the file, so the process that wrote it is the harness's helper, `inspect-sandbox`, started through `timeout -k 5s 180s .../inspect-sandbox-tools exec`. If you search the audit log for `echo` or `cat >`, you won't find the write. Search by path. Note the four seconds between the tool call and the write: that's the harness installing and starting its helper.

**6. The audit record shows the container's path.** The audit rule watches the host folder, `/srv/agent-output`. But the record for the write names `/output/status.txt`, the path as the process inside the container saw it. `docker inspect` connects the two: its `Mounts` entry maps `/srv/agent-output` to `/output`.

## Try it

<details><summary>1. Find the audit record for the curl process. What's its parent, and how do you know it belongs to this container?</summary>

Event 3909 at 14:53:21.326: `EXECVE` with `a0=curl`, `pid=11904`, `ppid=11898`. PID 11898 is `timeout` (event 3901), whose parent is `runc` (PID 11884, event 3899), whose parent is `containerd-shim-runc-v2` (PID 11528, event 3747) with `-id 57e6f530a89c71ff...`. That's the container ID in the Falco alert and in `docker-inspect-57e6f530a89c.json`.
</details>

<details><summary>2. How long after the transcript's timestamp for call_01 did the connection reach the service? Where did the time go?</summary>

About 168 ms: transcript 14:53:21.174, Zeek and Falco 14:53:21.342. Roughly 87 ms from the harness starting the call to Docker's `exec_create` (14:53:21.261), 57 ms more until `timeout` started (14:53:21.318), 8 ms through `bash` to `curl` (14:53:21.326), and 16 ms for `curl` to connect.
</details>

<details><summary>3. The service logged the request at 10:53:21 -0400. What's that in UTC, and does it match Zeek?</summary>

14:53:21 UTC. Zeek's `ts` is 1790693601.34, which is 14:53:21.34 UTC. They match to the second; the service log has no fractions.
</details>

<details><summary>4. Which process wrote status.txt, and what user did it run as?</summary>

`inspect-sandbox` (PID 12790), the harness's helper at `/var/tmp/.da7be258e003d428/inspect-sandbox-tools`, running as root (`uid=root`) inside the container. Its parent is `timeout -k 5s 180s ... exec` (PID 12784). Falco agrees: process `inspect-sandbox`, parent `timeout`.
</details>

## Where this fits

In the [playbook](https://docs.google.com/document/d/1qjdoAezkKrh4rZQlfZlpmzMFknomJhLCTR3UJ-Pg2BQ/edit), this is Q3 (agent log analysis) and Q4 (checking a hypothesis against other sources). Next: [worked example 3](../03-transcript-vs-reality/), where the layers disagree.
