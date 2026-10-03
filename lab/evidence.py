"""Turn a raw capture (from a capture.sh) into a responder's evidence folder.

What it does, and why each change is allowed:
  - Keeps only records about the agent sandboxes. Drops the lab's own collector
    and service containers, the capture machine's unrelated activity, and alerts
    caused by setting up the lab.
  - Replaces capture-machine details with the story's: the repo path becomes a
    job directory, bind-mount sources become their canonical host paths, the
    Falco hostname becomes the story's host, and local user names become "ci".
  - Never edits what the agent did or what the collectors saw. Transcripts are
    copied unchanged.

Every change is counted and returned as Markdown notes for the answer key.
Callers supply an EvidenceConfig; see scenarios/*/build/postprocess.py.
"""

import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ZEEK_KEEP = ["conn.log", "http.log", "files.log", "dns.log"]


@dataclass
class EvidenceConfig:
    sandbox_image: str  # image repository of the agent sandboxes, e.g. "kestrel/agent-sandbox"
    hostname: str  # the story's host name, used for Falco's hostname field
    build_dir_suffix: str  # repo-relative build dir, e.g. "/scenarios/01-build-cache/build"
    job_dir: str  # what the build dir becomes, e.g. "/opt/kestrel/agent-jobs"
    platform_dir: str  # what the repo root becomes
    mounts: dict[str, str]  # container mount destination -> canonical host path
    compose_vars: dict[str, str] = field(default_factory=dict)  # "${VAR:-x}" -> literal
    audit_keys: set[str] = field(default_factory=set)  # file-watch keys kept regardless of process
    service_logs: dict[str, str] = field(default_factory=dict)  # capture path -> evidence path
    listings: dict[str, str] = field(default_factory=dict)  # capture path -> evidence path


class _Notes:
    def __init__(self):
        self.lines: list[str] = []

    def add(self, file: str, what: str):
        self.lines.append(f"- `{file}`: {what}")


def _replacements(capture: Path, cfg: EvidenceConfig) -> list[tuple[str, str]]:
    repl: list[tuple[str, str]] = []
    for f in sorted((capture / "platform").glob("docker-inspect-*.json")):
        c = json.loads(f.read_text())[0]
        workdir = c["Config"]["Labels"].get("com.docker.compose.project.working_dir")
        if workdir:
            repl.append((workdir, cfg.job_dir))
            root = workdir.removesuffix(cfg.build_dir_suffix)
            if root != workdir:
                repl.append((root, cfg.platform_dir))
        for m in c.get("Mounts", []):
            canonical = cfg.mounts.get(m.get("Destination"))
            if canonical and m.get("Source") != canonical:
                repl.append((m["Source"], canonical))
    users = set(re.findall(r"/home/([a-z_][a-z0-9_-]*)", "\n".join(a for a, _ in repl)))
    repl += [(f"/home/{u}", "/home/ci") for u in users]
    return sorted(set(repl), key=lambda r: -len(r[0]))


def _scrub(text: str, repl) -> tuple[str, int]:
    count = 0
    for old, new in repl:
        n = text.count(old)
        if n:
            text, count = text.replace(old, new), count + n
    return text, count


def _events(capture: Path) -> list[dict]:
    return [json.loads(l) for l in (capture / "platform" / "docker-events.jsonl").read_text().splitlines()]


def _sandbox_ids(events, cfg) -> set[str]:
    return {
        e["Actor"]["ID"]
        for e in events
        if e.get("Type") == "container" and e["Actor"]["Attributes"].get("image", "").startswith(cfg.sandbox_image)
    }


def _window(events, ids) -> tuple[float, float]:
    times = [e["timeNano"] / 1e9 for e in events if e.get("Type") == "container" and e["Actor"]["ID"] in ids]
    return min(times) - 2, max(times) + 2


def _transcripts(capture, out, notes):
    dest = out / "transcripts"
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted((capture / "transcripts").glob("*.eval")):
        shutil.copy2(f, dest / f.name)
        notes.add(f"transcripts/{f.name}", "copied unchanged")
        with open(dest / (f.stem + ".json"), "w") as fh:
            subprocess.run(["inspect", "log", "dump", "--resolve-attachments", "full", str(f)], stdout=fh, check=True)
        notes.add(f"transcripts/{f.stem}.json", "readable copy of the .eval (`inspect log dump --resolve-attachments full`)")


def _docker(capture, out, notes, events, ids, repl, cfg):
    dest = out / "platform"
    dest.mkdir(parents=True, exist_ok=True)
    kept, dropped, replaced = [], Counter(), 0
    for e in events:
        attrs = e.get("Actor", {}).get("Attributes", {})
        if e["Actor"]["ID"] in ids or attrs.get("container") in ids:
            text, n = _scrub(json.dumps(e, separators=(",", ":")), repl)
            kept.append(text)
            replaced += n
        else:
            dropped[attrs.get("image") or attrs.get("name") or e.get("Type")] += 1
    (dest / "docker-events.jsonl").write_text("\n".join(kept) + "\n")
    notes.add(
        "platform/docker-events.jsonl",
        f"kept {len(kept)} events for the agent sandboxes; dropped "
        + ", ".join(f"{v} for `{k}`" for k, v in dropped.most_common())
        + f"; {replaced} path replacements in compose labels",
    )
    mount_sources = {old for old, new in repl if new in cfg.mounts.values()}
    for f in sorted((capture / "platform").glob("docker-inspect-*.json")):
        raw = f.read_text()
        text, n = _scrub(raw, repl)
        (dest / f.name).write_text(text)
        where = "compose labels, bind-mount source" if any(s in raw for s in mount_sources) else "compose labels"
        notes.add(f"platform/{f.name}", f"{n} path replacements ({where})")
    for f in sorted((capture / "platform").glob("compose-*.yaml")):
        text = f.read_text()
        for var, literal in cfg.compose_vars.items():
            text = text.replace(var, literal)
        (dest / f.name).write_text(text)
        notes.add(f"platform/{f.name}", "environment-variable defaults written out as literal paths" if cfg.compose_vars else "copied unchanged")


def _falco(capture, out, notes, repl, cfg):
    src = capture / "host" / "falco.jsonl"
    if not src.exists():
        return
    (out / "host").mkdir(parents=True, exist_ok=True)
    kept, dropped = [], Counter()
    for line in src.read_text().splitlines():
        alert = json.loads(line)
        if alert.get("output_fields", {}).get("container.image.repository", "") != cfg.sandbox_image:
            dropped[alert["rule"]] += 1
            continue
        alert["hostname"] = cfg.hostname
        kept.append(_scrub(json.dumps(alert, separators=(",", ":")), repl)[0])
    (out / "host" / "falco.jsonl").write_text("\n".join(kept) + "\n")
    notes.add(
        "host/falco.jsonl",
        f"kept {len(kept)} alerts from agent sandboxes; dropped lab-setup alerts: "
        + (", ".join(f"{v}× \"{k}\"" for k, v in dropped.most_common()) or "none")
        + f"; `hostname` (the Falco container's own name) set to `{cfg.hostname}`",
    )


def _zeek(capture, out, notes):
    dest = out / "network"
    dest.mkdir(parents=True, exist_ok=True)
    skipped = []
    for f in sorted((capture / "network" / "zeek").glob("*.log")):
        if f.name in ZEEK_KEEP:
            shutil.copy2(f, dest / f.name)
            notes.add(f"network/{f.name}", "copied unchanged")
        else:
            skipped.append(f.name)
    if skipped:
        notes.add("network/", "not included (Zeek's own housekeeping): " + ", ".join(f"`{s}`" for s in skipped))


def _copies(capture, out, notes, mapping, repl, what):
    for src_rel, dest_rel in mapping.items():
        src = capture / src_rel
        if not src.exists():
            notes.add(dest_rel, "NOT CAPTURED")
            continue
        text, n = _scrub(src.read_text(), repl)
        swaps = 0
        if what == "listing":
            for user, group in set(re.findall(r"^[d-][rwx-]{9}\s+\d+\s+(\S+)\s+(\S+)", text, re.M)):
                for name in {user, group} - {"root"}:
                    text, k = re.subn(rf"(?<=\s){re.escape(name)}(?=\s)", "ci", text)
                    swaps += k
        dest = out / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        if what == "listing":
            notes.add(dest_rel, f"`ls -la` after the runs; {swaps} owner names set to `ci`")
        else:
            notes.add(dest_rel, "copied unchanged (service local time, US Eastern)" if not n else f"{n} path replacements")


_AUDIT = re.compile(r"msg=audit\((\d+\.\d+):(\d+)\)")
_FIELD = re.compile(r'(\w+)=("[^"]*"|\S+)')


def _audit(capture, out, notes, ids, window, repl, cfg):
    src = capture / "host" / "audit.log"
    if not src.exists():
        notes.add("host/audit.log", "NOT CAPTURED in this run")
        return
    groups: dict[str, list[str]] = defaultdict(list)
    order, stamps = [], {}
    for line in src.read_text().splitlines():
        m = _AUDIT.search(line)
        if not m:
            continue
        # Event IDs restart when auditd restarts, so an event is (timestamp, ID), not ID alone.
        event = f"{m.group(1)}:{m.group(2)}"
        if event not in groups:
            order.append(event)
            stamps[event] = float(m.group(1))
        groups[event].append(line)

    # Walk the log in time order and decide membership when each process starts
    # (execve), from its parent's membership at that moment. PIDs get reused over
    # a long log, so a single pid -> process map built up front would be wrong.
    in_sandbox: dict[str, bool] = {}  # pid -> is the current process with this pid a sandbox process
    shims = 0
    start, end = window
    kept, dropped = [], Counter()
    for serial in order:
        recs = groups[serial]
        sc = next((r for r in recs if r.startswith("type=SYSCALL")), "")
        f = dict(_FIELD.findall(sc))
        pid, ppid = f.get("pid"), f.get("ppid")
        execve = next((r for r in recs if r.startswith("type=EXECVE")), "")
        if execve and pid:
            is_shim = "containerd-shim" in execve and any(cid in execve for cid in ids)
            shims += is_shim
            in_sandbox[pid] = is_shim or in_sandbox.get(ppid, False)
        member = bool(pid) and in_sandbox.get(pid, False)
        if not start <= stamps[serial] <= end:
            dropped["outside the run window"] += 1
        elif f.get("key", "").strip('"') in cfg.audit_keys or member:
            kept.append(serial)
        else:
            dropped["not from an agent sandbox or a watched path"] += 1

    (out / "host").mkdir(parents=True, exist_ok=True)
    text, n = _scrub("\n".join(l for s in kept for l in groups[s]) + "\n", repl)
    (out / "host" / "audit.log").write_text(text)
    notes.add(
        "host/audit.log",
        f"kept {len(kept)} events (processes descended from the sandboxes' `containerd-shim`, plus watched paths: "
        + ", ".join(sorted(cfg.audit_keys))
        + "); dropped "
        + ", ".join(f"{v} {k}" for k, v in dropped.items())
        + f"; {n} path replacements; {shims} sandbox shim starts found",
    )
    interp = subprocess.run(
        ["ausearch", "-if", str(out / "host" / "audit.log"), "-i"],
        capture_output=True,
        text=True,
        env={**os.environ, "TZ": "UTC"},
    )
    if interp.returncode == 0 and interp.stdout:
        (out / "host" / "audit-interpreted.txt").write_text(interp.stdout)
        notes.add("host/audit-interpreted.txt", "`ausearch -i` of the filtered audit.log, run with `TZ=UTC` so its times are UTC")
    else:
        notes.add("host/audit-interpreted.txt", "NOT GENERATED (ausearch unavailable or failed)")


def process(capture: Path, evidence: Path, cfg: EvidenceConfig) -> str:
    """Build `evidence` from `capture`. Returns Markdown processing notes.

    Builds into a staging folder next to `evidence` and replaces the old folder
    only once everything has succeeded, so a bad capture path or a failed step
    never destroys existing evidence.
    """
    for need in ("platform/docker-events.jsonl", "transcripts"):
        if not (capture / need).exists():
            raise FileNotFoundError(f"{capture} doesn't look like a capture: {need} is missing")
    staging = evidence.with_name(evidence.name + ".new")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        notes = _build(capture, staging, cfg)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if evidence.exists():
        shutil.rmtree(evidence)
    staging.rename(evidence)
    return notes


def _build(capture: Path, evidence: Path, cfg: EvidenceConfig) -> str:
    notes = _Notes()
    repl = _replacements(capture, cfg)
    events = _events(capture)
    ids = _sandbox_ids(events, cfg)
    if not ids:
        raise ValueError(f"no containers from image {cfg.sandbox_image!r} in {capture}/platform/docker-events.jsonl")
    window = _window(events, ids)

    _transcripts(capture, evidence, notes)
    _docker(capture, evidence, notes, events, ids, repl, cfg)
    _audit(capture, evidence, notes, ids, window, repl, cfg)
    _falco(capture, evidence, notes, repl, cfg)
    _copies(capture, evidence, notes, cfg.listings, repl, "listing")
    _zeek(capture, evidence, notes)
    _copies(capture, evidence, notes, cfg.service_logs, repl, "service")

    return "\n".join(
        [
            "# How the evidence was processed",
            "",
            f"Source: raw capture `{capture.name}`.",
            "",
            "Replacements applied everywhere they occurred:",
            "",
            *[f"- `{old}` → `{new}`" for old, new in repl],
            "",
            "Per file:",
            "",
            *notes.lines,
            "",
        ]
    )
