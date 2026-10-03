"""Quick check of a raw capture (or an evidence folder): what each collector recorded.

Usage (repo root, with the venv): python tools/summarize_capture.py <capture dir> [--all-execs]

Works for any capture made by a capture.sh in this repo. By default, harness
plumbing execs (OS probes, file copies) are counted but not listed.
"""

import glob
import json
import os
import re
import sys

from inspect_ai.log import read_eval_log

out = sys.argv[1]
all_execs = "--all-execs" in sys.argv


def lines(path):
    return open(path).read().splitlines() if os.path.exists(path) else []


print("== transcripts")
for f in sorted(glob.glob(f"{out}/transcripts/*.eval")):
    log = read_eval_log(f, resolve_attachments=True)
    s = log.samples[0]
    print(f"\n# {log.eval.task} status={log.status}")
    for e in s.events:
        if e.event == "tool":
            res = e.result if isinstance(e.result, str) else str(e.result)
            print(f"  [{e.timestamp:%H:%M:%S.%f}] {e.function} {json.dumps(e.arguments)[:110]}")
            print("     -> " + res.strip().replace("\n", "\n        ")[:600])

print("\n== docker events: agent tool execs")
counts = {}
for line in lines(f"{out}/platform/docker-events.jsonl"):
    ev = json.loads(line)
    attrs = ev.get("Actor", {}).get("Attributes", {})
    image, name = attrs.get("image", ""), attrs.get("name", "")
    action = ev.get("Action", "") or ev.get("status", "")
    key = (ev.get("Type"), action.split(":")[0], image or name)
    counts[key] = counts.get(key, 0) + 1
    if action.startswith("exec_create") and "agent-sandbox" in image:
        if all_execs or "bash --login -c" in action:
            print(f"  {ev['timeNano'] / 1e9:.3f} {name} {action[13:170]}")
print("  counts:")
for k, v in sorted(counts.items(), key=lambda kv: str(kv[0])):
    print("   ", v, k)

print("\n== falco")
for line in lines(f"{out}/host/falco.jsonl"):
    a = json.loads(line)
    of = a.get("output_fields", {})
    print(f"  {a['time']} {a['priority']} {a['rule']} | {of.get('container.name')} {str(of.get('proc.cmdline', ''))[:70]} {of.get('fd.name', '')}")

zeek = f"{out}/network/zeek" if os.path.isdir(f"{out}/network/zeek") else f"{out}/network"
print("\n== zeek conn")
for line in lines(f"{zeek}/conn.log"):
    c = json.loads(line)
    print(f"  {c['ts']} {c['id.orig_h']}:{c['id.orig_p']} -> {c['id.resp_h']}:{c['id.resp_p']} {c['proto']} {c.get('service')} {c.get('conn_state')} ob={c.get('orig_bytes')} rb={c.get('resp_bytes')}")
print("== zeek http")
for line in lines(f"{zeek}/http.log"):
    h = json.loads(line)
    print(f"  {h['ts']} {h.get('method')} {h.get('host')}{h.get('uri')} {h.get('status_code')} ua={h.get('user_agent')}")

for f in sorted(glob.glob(f"{out}/services/*.log")):
    print(f"== {os.path.relpath(f, out)}")
    print("  " + open(f).read().strip().replace("\n", "\n  "))
for f in sorted(glob.glob(f"{out}/host/*-listing.txt")):
    print(f"== {os.path.relpath(f, out)}")
    print("  " + open(f).read().strip().replace("\n", "\n  "))

audit = f"{out}/host/audit.log"
if os.path.exists(audit):
    print("== auditd")
    text = open(audit).read()
    for key in sorted(set(re.findall(r'key="([^"]+)"', text))):
        needle = 'key="' + key + '"'  # built outside the f-string so it runs on Python 3.11
        print(f"  records with key={key}: {text.count(needle)}")
    for line in lines(f"{out}/host/audit-interpreted.txt"):
        if "type=EXECVE" in line and "inspect_image_path" not in line and "expect=" not in line:
            print("  " + line.strip()[:200])
        elif "type=PATH" in line and ("/mnt/" in line or "/output" in line or "/srv/" in line):
            print("  " + line.strip()[:200])
else:
    print("== auditd: not captured")

for f in sorted(glob.glob(f"{out}/platform/docker-inspect-*.json")):
    d = json.load(open(f))[0]
    print(
        "inspect",
        os.path.basename(f),
        d["Name"],
        d["Config"]["Image"],
        [m.get("Source") + "->" + m.get("Destination") for m in d["Mounts"]],
        list(d["NetworkSettings"]["Networks"]),
        d["Config"]["Labels"].get("com.docker.compose.project"),
    )
