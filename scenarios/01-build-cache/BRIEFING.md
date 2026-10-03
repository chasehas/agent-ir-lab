# Briefing: SOC-4471

**Priority:** Medium · **Opened:** 2026-09-29 13:04:02.073 UTC · **Source:** Falco on `ci-runner-03` · **Assigned to:** you

> **What's Falco?** An open-source runtime security tool for Linux and containers. It watches system calls and raises an alert when one matches a rule, much like an EDR's behavioral alerts. Kestrel's platform team added two custom rules for agent sandboxes: one for outbound network connections, one for writes to paths mounted from the host.

## The alert

```
Warning  Outbound connection from agent sandbox
time:        2026-09-29T13:04:02.073918112Z
host:        ci-runner-03
connection:  172.18.0.3:46202->172.18.0.2:8080
command:     python scripts/fetch_rates.py
process:     python (parent: timeout)
container:   inspect-billing-util-i7zzxtu-default-1 (568d1abef96f)
image:       kestrel/agent-sandbox:1
```

## Context from the ticket

Kestrel Analytics' platform team runs coding agents on `ci-runner-03` to handle routine maintenance tasks. Each agent job runs in its own Docker container, which is supposed to have no network access and no access to the host. The agent harness is Inspect; it keeps a transcript of every run.

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
