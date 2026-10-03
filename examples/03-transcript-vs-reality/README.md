# Worked example 3: When the transcript and the host disagree

**Time:** about 20 minutes. **You need:** a text editor.

A tool result tells the agent what came back from a command. It doesn't tell anyone what the command actually did. This example is one short run where the agent's view and the host's view disagree, and the agent reports the wrong one.

## The run

An agent was asked to copy three release artifacts, a tarball, its checksum, and an SBOM, to a shared output folder. The SBOM didn't exist. The agent ran one `cp` command, got an error, and reported that the copy failed and nothing was copied.

This example uses the `ex-copy-artifacts` run in [`../evidence/`](../evidence/).

## Open it

Side by side:

- The transcript: `../evidence/transcripts/*ex-copy-artifacts*.json`, and its rendering, [transcript.md](transcript.md).
- `../evidence/host/agent-output-listing.txt`: the output folder after the runs.

Then check `../evidence/host/falco.jsonl` and `../evidence/host/audit-interpreted.txt`.

## What each side says

**The transcript.** One tool call, `cp dist/app-1.4.2.tar.gz dist/app-1.4.2.sha256 dist/app-1.4.2.sbom.json /output/`. The result:

```
cp: cannot stat 'dist/app-1.4.2.sbom.json': No such file or directory
```

The agent's reasoning: "The copy failed because the SBOM file doesn't exist." Its final answer: "...the copy failed and nothing was copied to /output."

**The host.** At 14:54:53.082 UTC, Falco raised two "Write to host-mounted path" alerts from that `cp`: one for `/output/app-1.4.2.tar.gz`, one for `/output/app-1.4.2.sha256`. The audit log has `cp` starting at 14:54:53.078 (event 4936) and creating both files in the same millisecond (events 4937 and 4938). The folder listing shows both files there.

**What happened.** `cp` copies each source it can and reports errors for the rest. It exits with an error if any source failed. Two of the three files were delivered. The tool result was accurate; it just contained only the error. The agent's reading of it was wrong, and its final answer passed that mistake on as fact.

## Things to notice

**1. A tool result is what came back, not what happened.** Error output is designed to report what went wrong. It says nothing about what went right before the failure.

**2. The agent's summary inherits its misreadings.** "Nothing was copied" is a confident, specific claim, and it's false. If you'd stopped at the final answer, you'd have the wrong picture of the output folder: two unexpected files that downstream jobs might pick up.

**3. Only outside evidence settles it.** The transcript alone can't tell you whether any files were copied. The Falco alerts, the audit records, and the listing can.

**4. Audit file names can be relative.** Look at events 4937 and 4938. The `PATH` records name the files as just `app-1.4.2.tar.gz` and `app-1.4.2.sha256`, and the parent directory as `/work` (the working directory). But `cp` opened them relative to the destination folder, not the working directory. The parent's inode, 869291, is the tell: it's the same inode as `/output/` in the `status.txt` write (event 4246). When a path looks wrong, check the inode.

**5. This is the same shape as scenario 01.** There, a script "failed" after its network request and host write had already happened. Look for the pattern: a command with several steps, an error at the end, and a summary that treats the whole thing as having done nothing.

## Try it

<details><summary>1. From the transcript alone, what's the most you can say about what was copied?</summary>

That the SBOM wasn't copied, because the error names it. Whether the other two files were copied isn't in the transcript. The result shows no output about them either way.
</details>

<details><summary>2. At what time were the two files written, and by which process?</summary>

14:54:53.078 UTC, by `cp` (PID 15045), the process the agent's single tool call started. Its parent is the harness's `timeout` wrapper (PID 15039). The tool call itself is timestamped 14:54:52.933 in the transcript.
</details>

<details><summary>3. What would you tell the release team?</summary>

That a partial set of 1.4.2 artifacts, the tarball and its checksum but no SBOM, was delivered to the output folder at 14:54:53 UTC, despite the agent reporting that nothing was copied. They should either remove them or finish the set before anything consumes the folder.
</details>

## Where this fits

In the [playbook](https://docs.google.com/document/d/1qjdoAezkKrh4rZQlfZlpmzMFknomJhLCTR3UJ-Pg2BQ/edit), this is Q4: validating a hypothesis, here the agent's own account, against other sources. Next: [worked example 4](../04-start-from-the-alert/), which starts from the host side.
