---
name: context-restore
description: Restore working context at the start of a session. Use at the beginning of a session or after a context compaction — reads the saved handoff snapshot, decisions log, and active experiments so work resumes accurately.
---

# context-restore

Rebuild working context from durable memory. Run this first when starting or
resuming, so the session is grounded in what actually happened rather than
guesses.

## When to use

First action of a new or resumed session; also after a context compaction to
re-anchor.

## Procedure

1. **Read the handoff** — `memory/session-latest.md`. This is the most recent
   stopping point: state, in-flight work, and the next step.

2. **Read the decisions log** — `memory/DECISIONS.md`. Scan recent entries so
   prior decisions are not relitigated or contradicted.

3. **Check active experiments** — `memory/experiments.md`. Note any run with no
   verdict — it may be running or abandoned; confirm before acting.

4. **Read the project context** — `AGENTS.md` (and any nested ones in the
   target project).

5. **Reconcile with reality** — Verify the snapshot against the current repo
   state (`git status`, `git log`). Memory reflects when it was written; if a
   file/branch it names has since changed, trust the repo and note the drift.

## Output

A short briefing: what the last session was doing, the immediate next step, and
any open question for the user. Then proceed. Pairs with [[context-save]].
