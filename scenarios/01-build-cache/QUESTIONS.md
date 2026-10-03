# Scenario 01: guided questions

Work through these in order. Each one says where to look. Write your answers down before you check the [answer key](answer-key/ANSWERS.md).

The goal isn't only to answer them. It's to notice which source answered each one. By the end, you should be able to say, for any claim you make about this incident, whether it rests on what the agent **said**, what it **asked to do**, what the platform **executed**, or what **happened outside** the sandbox.

---

**1. Which agent run caused the alert?**
Start from the alert in the [briefing](BRIEFING.md). Find the container in `evidence/platform/docker-events.jsonl` and `docker-inspect-*.json`, then find the matching transcript in `evidence/transcripts/`.
*Hint:* the transcript doesn't record a container ID. You'll have to join on something else.

**1a. Falco also raised Critical alerts in both runs that morning. What caused them, and do they matter here?**
Look at `evidence/host/falco.jsonl` and the process each alert names.

**2. Which tool call made the connection?**
Match the alert's time and command to the transcript's tool calls, and to the `exec_create` events in `docker events`.

**3. Where did the credential come from?**
Read the transcript from the start up to the tool call you found in question 2. Then check what `docker inspect` says about the container's mounts and network.

**4. How many times did the agent reach the rates service, and which file on the host did it change?**
The agent ran the fetch script three times; the last two had the token. The transcript says one of those two failed. Which of them actually had effects outside the sandbox? Use `evidence/network/`, `evidence/services/rates-access.log`, `evidence/host/falco.jsonl`, `evidence/host/audit.log`, and `evidence/host/build-cache-listing.txt`.
*Hints:* the rates service logs in its own local time. Falco and the audit log show paths as the container saw them (`/mnt/cache/...`); `docker inspect` tells you which host folder that is.

**5. What does the agent's final answer leave out?**
Compare its `submit` message with what you found in questions 2–4.

**6. What should you do now, and what else do you need to scope?**
List containment actions, and the questions you'd still need answered to know how far this goes.

**7. Separate the causes.**
What's the root cause? What are the contributing conditions? Which of your actions are containment, and which are remediation?
