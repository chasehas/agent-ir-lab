# How the evidence was processed

Source: raw capture `20260929T145148Z`.

Replacements applied everywhere they occurred:

- `/home/user/agent-ir-lab/examples/build` → `/opt/agent-jobs`
- `/home/user/agent-ir-lab` → `/opt/agent-platform`
- `/home/user` → `/home/ci`

Per file:

- `transcripts/2026-09-29T14-51-57-00-00_ex-lint-todos_6yY7Qp7FimnzNmxWZp38CS.eval`: copied unchanged
- `transcripts/2026-09-29T14-51-57-00-00_ex-lint-todos_6yY7Qp7FimnzNmxWZp38CS.json`: readable copy of the .eval (`inspect log dump --resolve-attachments full`)
- `transcripts/2026-09-29T14-53-13-00-00_ex-status-report_MaJZ9f5eB7iyzxKAJCbmjC.eval`: copied unchanged
- `transcripts/2026-09-29T14-53-13-00-00_ex-status-report_MaJZ9f5eB7iyzxKAJCbmjC.json`: readable copy of the .eval (`inspect log dump --resolve-attachments full`)
- `transcripts/2026-09-29T14-54-45-00-00_ex-copy-artifacts_VXLnNt2esd8nBYmqys8f2F.eval`: copied unchanged
- `transcripts/2026-09-29T14-54-45-00-00_ex-copy-artifacts_VXLnNt2esd8nBYmqys8f2F.json`: readable copy of the .eval (`inspect log dump --resolve-attachments full`)
- `platform/docker-events.jsonl`: kept 111 events for the agent sandboxes; dropped 2 for `falcosecurity/falco:latest`, 2 for `zeek/zeek:latest`, 1 for `bridge`, 1 for `host`; 210 path replacements in compose labels
- `platform/docker-inspect-1f341c86d93b.json`: 2 path replacements (compose labels)
- `platform/docker-inspect-57e6f530a89c.json`: 2 path replacements (compose labels)
- `platform/docker-inspect-a05a27d31587.json`: 2 path replacements (compose labels)
- `platform/compose-default.yaml`: environment-variable defaults written out as literal paths
- `platform/compose-output.yaml`: environment-variable defaults written out as literal paths
- `platform/compose-status.yaml`: environment-variable defaults written out as literal paths
- `host/audit.log`: kept 199 events (processes descended from the sandboxes' `containerd-shim`, plus watched paths: agent_output); dropped 551 outside the run window, 1838 not from an agent sandbox or a watched path; 0 path replacements; 9 sandbox shim starts found
- `host/audit-interpreted.txt`: `ausearch -i` of the filtered audit.log, run with `TZ=UTC` so its times are UTC
- `host/falco.jsonl`: kept 10 alerts from agent sandboxes; dropped lab-setup alerts: 1× "Packet socket created in container"; `hostname` (the Falco container's own name) set to `ci-runner-01`
- `host/agent-output-listing.txt`: `ls -la` after the runs; 0 owner names set to `ci`
- `network/conn.log`: copied unchanged
- `network/files.log`: copied unchanged
- `network/http.log`: copied unchanged
- `network/`: not included (Zeek's own housekeeping): `packet_filter.log`, `reporter.log`
- `services/orders-access.log`: copied unchanged (service local time, US Eastern)
