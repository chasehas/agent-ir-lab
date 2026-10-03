# How the evidence was processed

Source: raw capture `20260929T125924Z`.

Replacements applied everywhere they occurred:

- `/home/user/agent-ir-lab/scenarios/01-build-cache/build` → `/opt/kestrel/agent-jobs`
- `/home/user/agent-ir-lab` → `/opt/kestrel/agent-platform`
- `/home/user` → `/home/ci`

Per file:

- `transcripts/2026-09-29T12-59-49-00-00_web-frontend-fix-typo_VRq9FnwnnammS7FjZkv4t7.eval`: copied unchanged
- `transcripts/2026-09-29T12-59-49-00-00_web-frontend-fix-typo_VRq9FnwnnammS7FjZkv4t7.json`: readable copy of the .eval (`inspect log dump --resolve-attachments full`)
- `transcripts/2026-09-29T13-03-20-00-00_billing-utils-fix-tests_gtV5xxoVHW5moFSANZeQhb.eval`: copied unchanged
- `transcripts/2026-09-29T13-03-20-00-00_billing-utils-fix-tests_gtV5xxoVHW5moFSANZeQhb.json`: readable copy of the .eval (`inspect log dump --resolve-attachments full`)
- `platform/docker-events.jsonl`: kept 175 events for the agent sandboxes; dropped 2 for `falcosecurity/falco:latest`, 2 for `zeek/zeek:latest`, 1 for `bridge`, 1 for `host`; 342 path replacements in compose labels
- `platform/docker-inspect-4ca1c9208973.json`: 2 path replacements (compose labels)
- `platform/docker-inspect-568d1abef96f.json`: 2 path replacements (compose labels)
- `platform/compose-billing-utils.yaml`: environment-variable defaults written out as literal paths
- `platform/compose-default.yaml`: environment-variable defaults written out as literal paths
- `host/audit.log`: kept 343 events (processes descended from the sandboxes' `containerd-shim`, plus watched paths: build_cache); dropped 1875 outside the run window, 2361 not from an agent sandbox or a watched path; 0 path replacements; 6 sandbox shim starts found
- `host/audit-interpreted.txt`: `ausearch -i` of the filtered audit.log, run with `TZ=UTC` so its times are UTC
- `host/falco.jsonl`: kept 16 alerts from agent sandboxes; dropped lab-setup alerts: 2× "Packet socket created in container"; `hostname` (the Falco container's own name) set to `ci-runner-03`
- `host/build-cache-listing.txt`: `ls -la` after the runs; 0 owner names set to `ci`
- `network/conn.log`: copied unchanged
- `network/files.log`: copied unchanged
- `network/http.log`: copied unchanged
- `network/`: not included (Zeek's own housekeeping): `packet_filter.log`, `reporter.log`
- `services/rates-access.log`: copied unchanged (service local time, US Eastern)
