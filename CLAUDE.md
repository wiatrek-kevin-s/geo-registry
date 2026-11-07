# Project instructions: geo-registry.io (website, agent skill, connector)

**Scope.** These instructions apply only to building the geo-registry.io website, agent skill and connector (`site/`, `agent/`, the new CI jobs, `docs/`). Sessions doing registry work (entries, harvesters, health reviews) ignore this file.

You are building a static website, an agent skill and a read-only MCP connector, all generated from this repository's index. The plan was decided with the owner, Kevin (GitHub `wiatrek-kevin-s`), in advance. Carry it out faithfully, verify every step, and ask whenever the plan doesn't settle something. Don't redesign it: its decisions have reasons you may not see. The owner doesn't read code, so explain in plain words.

## Intent

> **For** GIS analysts and the AI agents they work with, **who** need to find what data covers a place, which tool does a job, and how each engine runs an operation, **the project** will put the whole geo-registry on its own website (own name and domain), browsable and searchable, honest about which entries are reviewed vs unverified, with an easy way to suggest fixes; plus one standalone agent skill, packaged for Claude, Codex/ChatGPT, Grok and Gemini, that turns "I want to do X" into what the person actually needs, asking questions or suggesting alternatives when the request doesn't fit the need. **We will know it works when** an analyst gets from a task ("lidar for Travis County", "buffer in PostGIS") to the right entry in under a minute; the site updates itself whenever the registry changes; the skill, installed in Claude and one other app, handles a set of test requests correctly, including asking when the request is unclear; and a stranger can open a fix from a link on the site. **It must** be cheap to host, stay in sync with the repo automatically, and keep accounts and domain in the owner's name. **It will not** have user logins, run geoprocessing, host copies of the data, or replace Columbus.

If the brief reads two ways, the reading that serves this intent wins; if both do, ask.

## Sources of truth

1. `docs/build-brief.md`: what to build and why. Each fact lives in one place; follow its IDs (D-n, REQ-n, F-n, H-n, Q-n) instead of guessing.
2. `docs/tasks.json`: the tasks. Change only `status` and `evidence`, so "done" keeps its meaning.
3. `docs/progress-log.md`: what has happened, newest handoff note first.
4. `docs/design-spec.md`: the look.

Nothing else is a source.

| Session | Tasks | Area | Checkpoint at end |
|---|---|---|---|
| S1 | T-1 to T-4 | Thin site and CI | Yes |
| S2 | T-5 to T-9 | Full site, look, domain, analytics | Yes |
| S3 | T-10 to T-13 | Agent skill | Yes |
| S4 | T-14 to T-18 | Connector and plugins | Yes |
| S5 | T-19 to T-21 | Upkeep and launch | Yes, then the final review |

## Start of every session

1. Read the newest handoff note, then the task list.
2. Check that the branch and last push match the log.
3. Run the smoke check: build the registry (`cd build && cargo run --release -- build --entries ../entries --schema ../schema/entry.schema.json --out ../dist`), then, once `site/` exists, the site build and its tests.
4. Tell the owner in two lines where things stand and what this session will do.
5. Do this session's tasks one at a time, in order, respecting `depends_on`. Don't start a task whose inputs are missing.
6. Write the handoff note as you go, not only at the end.

## Evidence

A task is done only when every acceptance check passes and you have recorded the evidence: a pointer (file, test output, CI run link, screenshot) plus one line of result. "Looks fine" is not evidence. Every task also meets the brief's definition of done. Never weaken a check to pass it; if a check is wrong, raise a change request.

For the owner's steps (H-1 to H-6), give click-by-click instructions in plain words, say exactly what to paste back, and wait.

Look up current docs, versions and prices before relying on them; the brief's research is dated 2026-11-07.

## Context

- One session is one area of work in one fresh chat.
- End the session and hand off when its tasks are done, or earlier if the chat has grown long, you are about to switch area, two attempts at a fix have failed, or you notice yourself repeating or unsure what was done.
- After any compaction, re-read these instructions, the newest handoff note and the task list before continuing.

## Saving work

Work on feature branches and land each task through a pull request (D-1, "Where the work happens"). Commit and push after every task, so a stopped session loses nothing. Any change can be reverted. Secrets never go into files or history, because history keeps them after deletion. Never rewrite history or force-push `main` without the owner's approval. Never touch anything the brief lists as "Out of bounds" (Where the work happens). You choose the commands. You work with the owner's GitHub sign-in, which has admin rights: never use them beyond the brief's "GitHub identity" rule.

## When to stop and ask

Stop, ask and wait when: a checkpoint is reached (brief, "Checkpoints"); a task needs homework or an open question settled; an assumption turns out false; the brief can be read two ways with different results; anything would change a decision, the scope, cost, security, privacy or the intent; or you are about to do anything on this list:

**Never without approval:** merging to `main` (every merge deploys to the public web, so merge only after the owner says so in the chat); spending money, upgrading a plan or signing up for anything; deleting releases, branches you didn't create, or history; changing repo settings, rulesets, secrets or environments (the owner does these); changing a format in "Formats that last" other than by adding fields; adding scope.

Never ask for passwords, tokens or other secrets in the chat; tell the owner where to enter them (GitHub environment secrets or repo variables).

**How to ask:** at most four questions at a time, each with 2–4 options, the recommended one first with its reason in one line, plus "You decide" and "Explain more first". Explain unfamiliar terms first. Never ask what you can look up.

**Recording changes:** decide small matters within the design yourself (brief, "Decide yourself") and log them with the reason. For a design change, write a change request in the log, ask, and act only once approved. A change touching a one-way door (marked in the brief's Decisions) is never approved here: mark it "Sent to Blueprint", pause the affected tasks and continue the rest.

## Final review

When every task is done and the definition of done is met, tell the owner: "Next is the final review: a fresh, sceptical reviewer runs the product and lists what's worth fixing. It changes nothing by itself." It runs in a new chat from `docs/final-review.md`. Fixes the owner chooses become `R-n` tasks; one re-check of those fixes follows.

## Style

Plain words, short sentences: what was done, what you need, what comes next.
