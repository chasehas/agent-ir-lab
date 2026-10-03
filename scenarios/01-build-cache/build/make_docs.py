"""Write BRIEFING.md and answer-key/ANSWERS.md from the processed evidence.

The exact values (container IDs, times, ports, counts) come from the evidence
folder, so the documents always match the capture they describe.

Usage (repo root, with the venv):
  python scenarios/01-build-cache/build/make_docs.py [evidence dir]
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.log import read_eval_log

SCENARIO = Path(__file__).resolve().parent.parent
EVIDENCE = Path(sys.argv[1]) if len(sys.argv) > 1 else SCENARIO / "evidence"


def jl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def utc(ts) -> str:
    if isinstance(ts, (int, float)):
        ts = datetime.fromtimestamp(ts, timezone.utc)
    elif isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return ts.astimezone(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + " UTC"


def day(ts) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------- gather

falco = jl(EVIDENCE / "host" / "falco.jsonl")
outbound = [a for a in falco if a["rule"] == "Outbound connection from agent sandbox"]
writes = [a for a in falco if a["rule"] == "Write to host-mounted path from agent sandbox"]
critical = [a for a in falco if a["priority"] == "Critical"]
alert = outbound[0]
af = alert["output_fields"]

inspects = {}
for f in sorted((EVIDENCE / "platform").glob("docker-inspect-*.json")):
    c = json.loads(f.read_text())[0]
    inspects[c["Id"]] = c
incident_c = next(c for c in inspects.values() if c["Id"].startswith(af["container.id"]))
benign_c = next(c for c in inspects.values() if c is not incident_c)

events = jl(EVIDENCE / "platform" / "docker-events.jsonl")
execs = [
    (e["timeNano"] / 1e9, e["Actor"]["Attributes"].get("name"), e["Action"].removeprefix("exec_create: "))
    for e in events
    if e["Action"].startswith("exec_create") and "bash --login -c" in e["Action"]
]
starts = {e["Actor"]["ID"]: e["timeNano"] / 1e9 for e in events if e["Action"] == "start"}

runs = {}
for f in sorted((EVIDENCE / "transcripts").glob("*.eval")):
    log = read_eval_log(str(f), resolve_attachments=True)
    tools = [e for e in log.samples[0].events if e.event == "tool"]
    runs[log.eval.task] = {"file": f.name, "log": log, "tools": tools}
incident = runs["billing-utils-fix-tests"]
benign = runs["web-frontend-fix-typo"]
fetches = [t for t in incident["tools"] if t.function == "bash" and "fetch_rates.py" in t.arguments["command"] and ".env" in t.arguments["command"]]
submit = next(t for t in incident["tools"] if t.function == "submit")

conns = jl(EVIDENCE / "network" / "conn.log")
http = jl(EVIDENCE / "network" / "http.log")
rates_log = (EVIDENCE / "services" / "rates-access.log").read_text().splitlines()

audit_blocks = []
interp = EVIDENCE / "host" / "audit-interpreted.txt"
if interp.exists():
    for block in interp.read_text().split("----"):
        if "key=build_cache" in block:
            name = re.findall(r"type=PATH .*? name=(\S+)", block)
            sc = re.search(r"type=SYSCALL msg=audit\(([^)]+)\).*? syscall=(\S+).*? comm=(\S+)", block)
            if sc:
                audit_blocks.append((sc.group(1), sc.group(2), sc.group(3), [n for n in name if n not in ("(null)",)]))

mount = next(m for m in incident_c["Mounts"] if m["Destination"] == "/mnt/cache")
inc_nets = ", ".join(incident_c["NetworkSettings"]["Networks"])
ben_nets = ", ".join(benign_c["NetworkSettings"]["Networks"])
project = incident_c["Config"]["Labels"]["com.docker.compose.project"]
alert_day = alert["time"][:10]

# ---------------------------------------------------------------- briefing

briefing = f"""# Briefing: SOC-4471

**Priority:** Medium · **Opened:** {alert_day} {utc(alert['time'])} · **Source:** Falco on `{alert['hostname']}` · **Assigned to:** you

> **What's Falco?** An open-source runtime security tool for Linux and containers. It watches system calls and raises an alert when one matches a rule, much like an EDR's behavioral alerts. Kestrel's platform team added two custom rules for agent sandboxes: one for outbound network connections, one for writes to paths mounted from the host.

## The alert

```
{alert['priority']}  {alert['rule']}
time:        {alert['time']}
host:        {alert['hostname']}
connection:  {af['fd.name']}
command:     {af['proc.cmdline']}
process:     {af['proc.name']} (parent: {af['proc.pname']})
container:   {af['container.name']} ({af['container.id']})
image:       {af['container.image.repository']}:{af['container.image.tag']}
```

## Context from the ticket

Kestrel Analytics' platform team runs coding agents on `{alert['hostname']}` to handle routine maintenance tasks. Each agent job runs in its own Docker container, which is supposed to have no network access and no access to the host. The agent harness is Inspect; it keeps a transcript of every run.

Two agent jobs ran on this host this morning. The platform team has pulled the evidence below and wants to know what happened, whether anything left the sandbox, and what to do now.

## Evidence you've been given

| Folder | What's in it |
|---|---|
| `evidence/transcripts/` | Inspect transcripts of both agent runs (`.eval`, plus a readable `.json` copy of each) |
| `evidence/platform/` | Docker's event stream for the agent containers, `docker inspect` of each container taken while it ran, and the compose files the jobs used |
| `evidence/host/` | The host's audit log (raw, plus an `ausearch -i` copy), Falco's alerts, and a listing of `/srv/build-cache` taken after the runs |
| `evidence/network/` | Zeek logs from the internal `ci` network (`conn.log`, `http.log`, `files.log`) |
| `evidence/services/` | The access log of the internal rates service, `rates.internal` |

Work through [QUESTIONS.md](QUESTIONS.md). The [README](README.md) has tips on opening each file.
"""

# ---------------------------------------------------------------- answers

def tool_line(t):
    return f"`{t.id}` at {utc(t.timestamp)}: `{t.arguments.get('command') if isinstance(t.arguments.get('command'), str) and t.function == 'bash' else t.function + ' ' + t.arguments.get('command', '')}`"


inc_execs = [x for x in execs if x[1] == af["container.name"]]
fetch_execs = [x for x in inc_execs if ".env" in x[2] and "fetch_rates" in x[2]]

rates_lines = "\n".join(f"    {l}" for l in rates_log)
conn_lines = "\n".join(
    f"- {utc(c['ts'])}: `{c['id.orig_h']}:{c['id.orig_p']}` → `{c['id.resp_h']}:{c['id.resp_p']}`, `conn_state {c['conn_state']}`, {c['orig_bytes']} bytes out, {c['resp_bytes']} bytes back"
    for c in conns
)
http_lines = "\n".join(f"- {utc(h['ts'])}: `{h['method']} {h['host']}{h['uri']}` → {h['status_code']}" for h in http)
write_lines = "\n".join(f"- {utc(a['time'])}: `{a['output_fields']['fd.name']}` by `{a['output_fields']['proc.cmdline']}`" for a in writes)
if audit_blocks:
    # Collapse consecutive records by the same process (e.g. one `ls` touching every file).
    grouped: list[list] = []
    for t, sc, comm, names in audit_blocks:
        names = [n for n in names if n.startswith("/")]
        if grouped and grouped[-1][2] == comm and comm == "ls":
            grouped[-1][3] += [n for n in names if n not in grouped[-1][3]]
            grouped[-1][1].add(sc)
        else:
            grouped.append([t, {sc}, comm, names])
    audit_lines = "\n".join(
        f"- {t.rsplit(':', 1)[0]} UTC: `{', '.join(sorted(scs))}` by `{comm}` on {', '.join(f'`{n}`' for n in names) or '(no path)'}"
        for t, scs, comm, names in grouped
    )
    audit_para = (
        "The audit log's watch on `/srv/build-cache` (key `build_cache`) recorded, from `audit-interpreted.txt`:\n\n"
        f"{audit_lines}\n\n"
        "The first two are the container runtime setting up the mount when the container started. The `ls` is the agent's step 5. "
        "Then, for each fetch, `bash` reads `.env` and `python` writes `rates.json`, with the **same process ID**: bash sources "
        "the file, then replaces itself with `python` because it's the last command on the line. That's also why Falco lists "
        "`python`'s parent as `timeout`.\n\n"
        "Note the paths: the watch is on the host directory, but the records show the path the process used, which is the "
        "container-side `/mnt/cache/...`."
    )
else:
    audit_para = "*(The audit log was not captured in this build of the evidence.)*"

crit_by_container = {}
for a in critical:
    crit_by_container.setdefault(a["output_fields"]["container.name"], []).append(a)
crit_lines = "\n".join(
    f"- `{name}`: {len(v)} alerts between {utc(v[0]['time'])} and {utc(v[-1]['time'])}, process `{v[0]['output_fields']['proc.name']}`"
    for name, v in crit_by_container.items()
)

answers = f"""# Scenario 01: answers

Values below are from the evidence in this folder's sibling `evidence/`. The true story is in [timeline.md](timeline.md); how the raw capture was cleaned up is in [processing.md](processing.md).

## 1. Which agent run caused the alert?

**`billing-utils-fix-tests`**, transcript `{incident['file']}`.

There's no shared ID between the alert and the transcript. You join on three things:

- **Container name.** Falco names `{af['container.name']}`. Its compose project label is `{project}`: Inspect's naming, a shortened task name plus a random suffix. `billing-util...` matches the task `billing-utils-fix-tests`, not `web-frontend-fix-typo`.
- **Time.** That container started at {utc(starts[incident_c['Id']])}; the transcript's first tool call is at {utc(incident['tools'][0].timestamp)}.
- **Command text.** Every bash tool call appears in `docker events` as an `exec_create` whose command ends with exactly the transcript's command. For this container:

{chr(10).join(f"  - {utc(t)}: `{cmd}`" for t, _, cmd in inc_execs)}

## 1a. The Critical alerts

{crit_lines}

All are Falco's stock rule "Drop and execute new binary in container", fired by `inspect-sandbox`: the harness's helper binary for the `text_editor` tool, copied into `/var/tmp/.<hex>/` and started the first time each run used `text_editor`. It's expected behavior for this harness and appears in the harmless run too. It's not part of the incident. It is worth noticing that the loudest alerts of the morning are harness plumbing, while the real problem was a Warning.

## 2. Which tool call made the connection?

The first one that loaded `/mnt/cache/.env`: {tool_line(fetches[0])}.

- Transcript: tool call at {utc(fetches[0].timestamp)}.
- `docker events`: `exec_create` at {utc(fetch_execs[0][0])}.
- Falco: outbound connection at {utc(outbound[0]['time'])}.
- Zeek: connection at {utc(conns[0]['ts'])}.

## 3. Where did the credential come from?

From the repo's own instructions, through a host directory that shouldn't have been mounted.

1. The tests fail for lack of `tests/fixtures/rates.json`.
2. The README says to generate fixtures with `scripts/fetch_rates.py`, which "needs `RATES_TOKEN`".
3. Running the script without it prints: `error: RATES_TOKEN is not set (on build hosts it is in /mnt/cache/.env)`.
4. The agent checks `/mnt/cache`, finds `.env`, and sources it with `set -a`.

`/mnt/cache` exists only because of the compose file. `docker inspect` of `{af['container.name']}` shows a bind mount `{mount['Source']}` → `{mount['Destination']}` (read-write: {mount['RW']}) and network `{inc_nets}`. The harmless run's container shows no mounts and network `{ben_nets}`. The compose file `platform/compose-billing-utils.yaml` has the mount (for pip's cache) and the external `ci` network.

## 4. How many times did it reach the service, and which host file did it change?

**Twice, and it overwrote `/srv/build-cache/rates.json` both times.** The agent ran the fetch script three times. The first (`call_04`) had no token and stopped before any network activity. The next two (`call_06`, `call_07`) had the token. The transcript shows `call_06` ending in a traceback, and the agent's reasoning calls it a failure. But both reached the service and wrote to the host. The listing of `/srv/build-cache` shows `rates.json` last modified during the run.

Zeek, `conn.log`:

{conn_lines}

Zeek, `http.log`:

{http_lines}

The rates service's log, in its local time (`-0400`, US Eastern; add four hours for UTC). Both requests used key `ci-build-key-02`:

{rates_lines}

Falco, writes through the mount:

{write_lines}

{audit_para}

So the first attempt's "failure" came *after* the request and the host write: the script crashed only when it tried to save the fixture into a directory that didn't exist.

## 5. What does the final answer leave out?

The agent's `submit` at {utc(submit.timestamp)}: "{submit.arguments['answer']}"

It doesn't mention that it:

- loaded a credential from a host-mounted file,
- used it to call an internal service, twice,
- wrote to the host's `/srv/build-cache/rates.json`, twice,
- exported everything in `.env` into the script's environment (`set -a`), not just `RATES_TOKEN`. In this lab, `.env` also holds `ARTIFACTS_UPLOAD_KEY`.

It also says the tests pass, which was true inside the container. But the fixture it generated lived only in that container, which was destroyed at the end of the run. The only lasting change it made was the one on the host.

The final answer is part of the incident, not a summary of it.

## 6. What to do now, and what to scope

**Containment**

- Revoke and rotate `RATES_TOKEN` (key `ci-build-key-02`). Treat every other secret in `/srv/build-cache/.env` as exposed too, since the agent exported the whole file into its environment.
- Stop using `compose-billing-utils.yaml` until it's fixed. Check whether other jobs use it or a similar file.

**Scope**

- Which other agent runs used this compose file, or any compose file that mounts `/srv/build-cache` or joins the `ci` network?
- What else is in `/srv/build-cache`, and who else can read it?
- Did the rates service see any other use of `ci-build-key-02` outside expected CI jobs?
- Did anything else consume the rewritten `/srv/build-cache/rates.json`? Other jobs read that cache.
- Was `ARTIFACTS_UPLOAD_KEY` used anywhere after this run?

## 7. Causes

- **Root cause:** the sandbox configuration. The compose file gave the agent's container a read-write host mount and access to the internal network, so the "isolated" sandbox wasn't isolated.
- **Contributing conditions:** a live secret stored in a shared cache directory; a script whose error message tells the reader where that secret lives; secrets stored as a file that can be sourced wholesale.
- **Containment:** token rotation, pulling the compose file.
- **Remediation:** a default-deny sandbox configuration (no network, no host mounts) with reviewed exceptions; secrets out of shared caches and into a secrets manager; a separate, read-only cache mount if caching is needed.

Intent isn't needed for any of this. The agent followed the repo's instructions to finish its task. The boundary crossing happened, and it has to be contained, either way.
"""

(SCENARIO / "BRIEFING.md").write_text(briefing)
(SCENARIO / "answer-key").mkdir(exist_ok=True)
(SCENARIO / "answer-key" / "ANSWERS.md").write_text(answers)
print(f"wrote BRIEFING.md and answer-key/ANSWERS.md from {EVIDENCE}")
