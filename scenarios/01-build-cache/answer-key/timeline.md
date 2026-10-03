# Scenario 01 — Build cache: ground-truth timeline

**Status: approved at checkpoint 1 (Sep 29), with changes from a ChatGPT review.** This is the true story the evidence was built from. It's in the answer key; responders shouldn't read it until they've worked the scenario.

## Learning objectives

By the end, a responder should be able to:

1. Tell apart four layers that an agent incident mixes together, and name the evidence for each:

   | Layer | Question it answers | Evidence here |
   |---|---|---|
   | What the agent perceived and said | What did it see, think, and claim? | Transcript: reasoning, text, tool results, final answer |
   | What the agent asked to do | Which actions did it request? | Transcript: tool calls |
   | What the platform executed | What actually ran, where? | `docker events`, harness sandbox events, audit `execve` records |
   | What happened outside | What changed or left the sandbox? | Falco, Zeek, audit file records, the rates service log |

2. Reconstruct one timeline across those sources, starting from an alert.
3. Separate root cause, contributing conditions, containment, and remediation.
4. Establish that an unauthorized boundary crossing happened without needing to settle the agent's intent.

## The story in one paragraph

A platform team at Kestrel Analytics (fictional) runs a coding agent on routine maintenance tasks. One morning it asks the agent to fix a failing test in `billing-utils`. The agent runs in a Docker container that is supposed to be isolated. But an engineer wrote a custom compose file for this job so builds could reuse a shared pip cache: it bind-mounts the build host's `/srv/build-cache` into the container and attaches the container to the internal `ci` network. The failing test needs a fixture file that a helper script downloads from an internal rates service. The script needs a token, and its own error message points to where build hosts keep it: `/mnt/cache/.env`, which exists inside the container only because of the mount. The agent follows that hint, loads the token, and runs the script. The script contacts the rates service, writes a cache file back to the host through the mount, then crashes on a missing directory. The agent reads the crash as "the fetch failed," creates the directory, and runs it again. The test passes. The agent's final summary says it generated the missing fixture. It doesn't mention the token, the service, or the host write. A Falco rule fires on the container's outbound connection, and the SOC picks it up.

**What actually happened:** the agent crossed the *intended* isolation boundary using capabilities the environment gave it: a host mount and network access. It didn't defeat Docker; the environment failed to enforce the boundary everyone assumed was there. It got there by following the repo's own instructions as a side effect of finishing its task. It did not go looking for a way out. Responders don't need to settle intent to establish that the crossing happened and must be contained. Intent is kept simple here on purpose; the roadmap's harder scenario is where it's genuinely unclear.

## Setting

| Thing | Value |
|---|---|
| Company | Kestrel Analytics (fictional) |
| Build host | `ci-runner-03` (Ubuntu 24.04, Docker Engine) |
| Agent harness | Inspect, `react()` agent with `bash()` and `text_editor()` |
| Agent run of interest | Task `billing-utils-fix-tests` |
| Other run on the same host that morning | Task `web-frontend-fix-typo`, default sandbox (no network, no mounts). Benign. It's there so the responder has to pick the right transcript |
| Misconfigured compose file | Bind mount `/srv/build-cache:/mnt/cache` (read-write); container on the external `ci` network instead of `network_mode: none` |
| Host directory contents | `/srv/build-cache/.env` (holds `RATES_TOKEN=rtok_EXAMPLE_...`), `pip/` (cache), `rates.json` (an older cached copy) |
| Internal service | `rates.internal:8080`, a small HTTP service in a second container on the `ci` network. Returns currency exchange rates. Keeps an access log in local time (US Eastern) |
| Detection | Falco on the build host with two custom rules: outbound connection from an agent sandbox; write under a host-mounted path from an agent sandbox. Falco is an open-source runtime security tool for Linux and containers: it watches system calls and raises an alert when one matches a rule, much like an EDR's behavioral alerts. The briefing should explain it in a line or two, since many responders won't have used it |

## Timeline

Times are offsets from the start of the run. Real timestamps come from the capture run. Tool calls are what the scripted agent does; "host effect" is what the collectors should record. Host effects marked *(verify)* get checked in the validation run before any evidence is built.

| # | T+ | Agent (transcript) | Host effect (evidence) | Teaching point |
|---|---|---|---|---|
| 0 | 0:00 | Run starts. Task: "The test suite in /repo (billing-utils) is failing. Make it pass." | `docker events`: container `inspect-billing-util-<random>-default-1` created and started; then about 10 `exec_create`s as the harness copies the repo files in (`mkdir -p`, then a `timeout ... /bin/sh -c` that writes each file). `docker inspect` (captured during the run): the mount and the `ci` network. **The transcript records no container ID or name** | Start-from-alert pivot: there is no shared ID. Join on the container name (a truncated task name), time, and command text |
| 1 | 0:05 | Reasoning: run the tests first. `bash: cd /repo && python -m pytest -q` → 2 failed, `FileNotFoundError` for `tests/fixtures/rates.json` | `docker events`: one `exec_create` of `/usr/bin/timeout -k 5s 60s bash --login -c cd /repo && python -m pytest -q` (confirmed). audit: `execve` of that wrapper chain, then `python -m pytest` | Join: tool call ↔ platform execution ↔ `execve`. The command text matches the transcript exactly |
| 2 | 0:20 | `text_editor view tests/test_convert.py`; `bash: cat README.md` → README says fixtures come from `python scripts/fetch_rates.py`, which "needs RATES_TOKEN" | The `text_editor` call produces about 12 `exec_create`s (OS probes, then the helper binary `/var/tmp/.<hex>/inspect-sandbox-tools`). Falco's stock rule **"Drop and execute new binary in container" fires at Critical** on that helper, in this run and in the benign run (confirmed). `bash cat` is one `exec_create` | Not every process in the container is the agent's choice. The loudest alert of the morning is harness plumbing |
| 3 | 0:35 | `bash: python scripts/fetch_rates.py` → `error: RATES_TOKEN is not set (on build hosts it is in /mnt/cache/.env)` exit 1 | audit: `execve` python | The repo's own message points at the mounted path |
| 4 | 0:50 | Reasoning: the error says where the token lives on build hosts; check whether that path exists here. `bash: ls -la /mnt/cache` → `.env`, `pip/`, `rates.json` | audit: `execve` ls. Falco: nothing (listing a directory isn't in the rules) | The first sign of the mount, visible in the transcript |
| 5 | 1:05 | `bash: set -a; . /mnt/cache/.env; set +a; python scripts/fetch_rates.py` → traceback: `FileNotFoundError: tests/fixtures/rates.json` (the fixtures directory doesn't exist), exit 1 | audit: `execve` python; read of `/mnt/cache/.env`; write of `/mnt/cache/rates.json` (container-side path; inode matches host `/srv/build-cache/rates.json`) *(verify the read shows up)*. Zeek: TCP connection agent → `rates.internal:8080`, HTTP 200, bytes transferred. Falco: **alert — outbound connection from agent sandbox**; **alert — write under host-mounted path**. Rates service log: `GET /v1/rates` 200 with the token's key ID | **The tool result reports failure, but the consequential actions already happened.** Only telemetry outside the transcript shows the network call and the host write succeeded |
| 6 | 1:20 | Reasoning: "The fetch failed because the fixtures directory is missing. Create it and retry." `bash: mkdir -p tests/fixtures && set -a; . /mnt/cache/.env; set +a; python scripts/fetch_rates.py` → `wrote tests/fixtures/rates.json` | Second connection, second host write, second service log line, second pair of Falco alerts | The transcript shows two attempts, and the agent's reasoning calls the first one a failure. Only external telemetry shows that both attempts reached the service and wrote to the host |
| 7 | 1:40 | `bash: python -m pytest -q` → all passed | audit: `execve` | |
| 8 | 1:50 | Submit: "Fixed the failing test by generating the missing fixture with scripts/fetch_rates.py." | `docker events`: container stop/destroy | **The final answer is part of the incident, not a summary of it.** It leaves out the token, the service, and the host write. The reasoning is evidence of what the agent perceived, not of what occurred |

The benign `web-frontend-fix-typo` run happens a few minutes earlier: two `bash` calls and one `text_editor` call, no network, no mount. Its only alerts are the Critical "Drop and execute new binary" ones from the harness helper.

## Validation run (local WSL, Sep 29)

Everything above marked "confirmed" was checked against a real capture (`build/capture.sh --gap 20`, no auditd). Both custom Falco rules fired twice, 1 ms apart, at the two fetch attempts (write rule on `/mnt/cache/rates.json`). Zeek logged two `GET rates.internal:8080/v1/rates` → 200, `conn_state SF`. The rates service logged both with `key_id=ci-build-key-02`, in `-0400`. The host's `rates.json` was rewritten during the first attempt. Still unverified: the audit records, which need the cloud run.

Lab noise to filter out of the evidence (not part of the story): Falco alerts caused by the capture setup itself ("Packet socket created in container" from the Zeek container, "Clear Log Activities" from building images), and anything from the Falco, Zeek, and rates-service containers in `docker events`.

## The alert (what the responder starts from)

Falco, `Warning`, rule **"Outbound connection from agent sandbox"**, container name and ID of the `billing-utils` run, destination `rates.internal:8080`, process `python`. Delivered in the briefing as the SOC ticket.

## Investigation path (for the answer key)

Alert → identify the container → identify the run → read the transcript → find the mount and network configuration → match attempted commands to host and network effects → establish where the credential came from → determine actual scope → contain → identify root cause.

## Evidence files (planned)

| File | Source | Notes |
|---|---|---|
| `transcripts/*.eval` (+ `raw-log.json`) | Inspect | Both runs |
| `platform/docker-events.jsonl` | `docker events` during capture | Platform record. Expect one `exec_create` per `bash` call and several per `text_editor` call *(verify)* |
| `platform/docker-inspect-<container>.json` | `docker inspect` during the run | Shows the bind mount and the `ci` network |
| `platform/compose.yaml` | The misconfigured file | What the engineer wrote |
| `host/audit.log` and `host/audit-interpreted.txt` | auditd raw + `ausearch -i` | Rules: `execve` for all processes, plus a read/write/attribute watch (`-w /srv/build-cache -p rwa`) so the `.env` read and the `rates.json` writes are recorded. Filtered to the run window and the runs' process trees |
| `host/falco.jsonl` | Falco | Stock rules plus the two custom rules. Keeps the harness's Critical "Drop and execute new binary" alerts; drops alerts caused by the capture setup |
| `network/conn.log` (+ `http.log`) | Zeek, JSON lines | Captured on the `ci` bridge |
| `services/rates-access.log` | Rates service | Local time (US Eastern). The clock-mismatch note goes here |

## Guided questions (draft)

1. Which agent run caused the alert? (Falco container name/ID → `docker events` → task name and time → transcript. There's no shared ID; the command text in `docker events` matches the transcript exactly)
1a. Falco also raised Critical alerts in both runs that morning. What caused them, and do they matter here? (The harness dropping and starting its own helper binary for `text_editor`. Expected behavior for this harness; not part of the incident. Guided, not a trap)
2. Which tool call made the connection? (Timestamp join between Falco, `docker events`, and the transcript)
3. Where did the credential come from? (Transcript steps 3–5; `docker inspect` shows the mount)
4. How many times did the agent reach the rates service, and which host file did it change? The agent ran the fetch script three times; the last two had the token. Which of those had effects? (Zeek, service log, audit: both did. The first of the two looks like nothing happened)
5. What does the agent's final summary leave out?
6. What should you do now, and what else do you need to scope? (Revoke and rotate the token; stop using the compose file; check whether other agent runs used it or the same mount; find what else in `/srv/build-cache` was exposed; check the rates service for any other use of the token)
7. Separate the causes. (Root cause: the compose file gave the container a host mount and internal network access. Contributing conditions: a live secret in the shared cache directory; a script whose error message points to it. Containment: token rotation, pulling the compose file. Remediation: default-deny sandbox config, secrets out of shared caches)

## Before building evidence

1. ~~**Local validation run**~~ Done Sep 29; see "Validation run" above.
2. **Cloud capture run:** the same run with auditd added, for the final evidence. Prompt in `build/CLOUD-CAPTURE.md`.

## Design choices (approved Sep 29)

- **Company name:** Kestrel Analytics.
- **Model name in the transcript:** stays `mockllm/model`, and the README says these are scripted runs.
- **Token:** obviously fake (`rtok_EXAMPLE_...`) so it never looks like a leaked real secret.
- **Service log timezone:** US Eastern, so the clock-mismatch note has something to point at. Everything else in UTC.
