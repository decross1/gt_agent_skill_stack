---
name: context-save
layer: C
runtime-safe: false
description: Save the current working session to durable memory before ending or switching tasks. Use when wrapping up, hitting a context limit, or pausing work — writes a handoff snapshot so the next session resumes without re-deriving everything.
---

# context-save

Persist what matters from this session to a file so it survives across sessions
and across harnesses (Pi or Claude Code). The runtime's own memory may not carry
over — these files always do.

## When to use

End of a work session, before a long pause, when context is about to be
compacted, or when handing off.

## Procedure

Write a snapshot to `memory/session-latest.md` (overwrite it — it is the *current*
handoff, not a log). Include:

- **Date & task** — What this session was working on.
- **State** — What is done, what works, what is verified.
- **In flight** — What is half-done, and the exact next step to take.
- **Open questions / blockers** — Decisions pending, things waiting on the user.
- **Key context** — Non-obvious facts discovered this session that the next
  session would otherwise have to rediscover (file locations, gotchas, why an
  approach was rejected).
- **Pointers** — Relevant run IDs, PRs, branches, commits.

Then:

- If any durable *decision* was made, append it to `memory/DECISIONS.md` — that
  file is the permanent record; `session-latest.md` is transient.
- If an experiment is mid-flight, ensure its [[experiment]] entry is current.

## Rule

Write the snapshot so a fresh session — possibly in the other harness — can read
it and continue with no further explanation. Restore it with [[context-restore]].
