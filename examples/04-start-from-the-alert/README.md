# Worked example 4: Starting from the alert

**Time:** about 20 minutes. **You need:** a text editor. `jq` helps.

Examples 2 and 3 started from the transcript. A SOC analyst usually starts from the other end: an alert on a host. This example works backwards from a Falco alert to the agent run and the exact tool call behind it, then decides whether it matters.

## The alert

```
Notice  Outbound connection from agent sandbox
time:        2026-09-29T14:53:21.341939490Z
host:        ci-runner-01
connection:  172.19.0.3:41878->172.19.0.2:8080
command:     curl -s -w \nHTTP %{http_code}\n http://orders.internal:8080/health
process:     curl (parent: timeout)
container:   inspect-ex-status-re-icupxox-default-1 (57e6f530a89c)
image:       lab/agent-sandbox:1
```

Three agent runs happened on this host in the same few minutes. All their evidence is in [`../evidence/`](../evidence/).

## The pivot

**1. Alert → container.** The alert names the container. Open `../evidence/platform/docker-inspect-57e6f530a89c.json` and check its mounts and network. Is this container supposed to reach the network at all? Its compose file is named in the `com.docker.compose.project.config_files` label.

**2. Container → run.** The transcript doesn't record a container ID, so join on what the two share:

- **Name.** Inspect names containers `inspect-<shortened task name>-<random>-default-1`. `ex-status-re...` matches one of the three transcripts.
- **Time.** In `docker events`, the container's `start` comes a few seconds before that transcript's first tool call.
- **Command text.** The `exec_create` events on that container end with exactly the commands in that transcript's tool calls.

**3. Run → tool call.** In that transcript, find the tool call whose timestamp comes just before the alert and whose command matches the alert's `command` field.

**4. Decide.** Read the tool call in context: the task, the reasoning before it, and what the agent did with the result. Then check the outside evidence (Zeek, the service's log) to see what the connection actually was.

## Things to notice

**1. There's no shared ID.** Every pivot from host to transcript is a join on name, time, and command text. It works here because each command is distinctive. When an agent runs the same command in several runs, time does most of the work.

**2. The alert is on legitimate activity.** This run was supposed to reach the service. Its compose file, `compose-status.yaml`, puts it on the internal `lab` network and mounts the output folder, on purpose. The rule that fired is doing its job; the context is what makes it benign. Compare scenario 01, where the same kind of rule fires on a container that wasn't supposed to have any network.

**3. The transcript gives you intent-shaped context, not proof.** The task and reasoning say *why* the agent made the call. Zeek and the service's log say *what* the call was. You need both to close the alert.

**4. The loudest alerts aren't this one.** Nine seconds later, the same run triggered six of Falco's stock **Critical** "Drop and execute new binary" alerts, from the harness's own helper. Triage by priority alone would have sent you somewhere else first.

## Try it

<details><summary>1. Which run caused the alert, and which tool call?</summary>

The `ex-status-report` run (`*ex-status-report*.eval`), tool call `call_01`: `curl -s -w '\nHTTP %{http_code}\n' http://orders.internal:8080/health`.

- The container started at 14:53:13.729 UTC (`docker events`, `timeNano` 1790693593728896745); the transcript's first tool call is at 14:53:21.174.
- `docker events` has the `exec_create` for that exact command at 14:53:21.261.
- Falco saw the connection at 14:53:21.342.
</details>

<details><summary>2. The other two runs: did either of them touch the network?</summary>

No. `ex-lint-todos` and `ex-copy-artifacts` both have `network_mode: none` (their `docker inspect` shows network `none`; their compose files say so). Zeek saw exactly one connection in the whole capture, this one. `ex-copy-artifacts` does have the output folder mounted, which is why it shows up in Falco's write alerts, but not on the network.
</details>

<details><summary>3. Would you close this alert? What would you write in the ticket?</summary>

Yes, as expected activity. Something like: "Outbound connection from `inspect-ex-status-re-icupxox-default-1` at 14:53:21 UTC was the `ex-status-report` agent job checking `orders.internal:8080/health`, its assigned task. The job's compose file allows access to the `lab` network. Zeek and the orders service's log show one `GET /health` → 200 with a 76-byte body. No further action. Consider a rule exception for this job's health check so it doesn't page again."
</details>

## Where this fits

In the [playbook](https://docs.google.com/document/d/1qjdoAezkKrh4rZQlfZlpmzMFknomJhLCTR3UJ-Pg2BQ/edit), this is triage (Phase 1) feeding D1: whether to declare an incident. Next: [scenario 01](../../scenarios/01-build-cache/), where you do all of this end to end.
