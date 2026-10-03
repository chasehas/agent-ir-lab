# Worked examples

Short, focused lessons. Do them in order; each builds on the one before.

| Example | The point |
|---|---|
| [1. Anatomy of a transcript](01-anatomy/) | A transcript has parts, and each one tells you something different. The tool call is not the process |
| [2. Matching the transcript to the host](02-join/) | The join key is the command text. Convert every clock to UTC before you compare |
| [3. When the transcript and the host disagree](03-transcript-vs-reality/) | A tool result is what came back, not what happened. The agent's summary inherits its mistakes |
| [4. Starting from the alert](04-start-from-the-alert/) | There's no shared ID between an alert and a transcript. Join on name, time, and command |

Example 1 has its own evidence. Examples 2–4 share the evidence in [`evidence/`](evidence/): three short agent runs on one host, a few minutes apart.

When you're done, try [scenario 01](../scenarios/01-build-cache/).
