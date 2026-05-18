---
name: gate-check
description: Check for human gates, human-only tasks, and blocking conditions before a consequential action. Use before executing any plan step, irreversible operation, publication, or anything that may need human approval — it halts and prints rather than proceeding past a gate.
---

# gate-check

The discipline that keeps an agent inside its authority. Before doing something
consequential, stop and ask: *is there a gate here?* If yes, **halt and print** —
do not proceed, do not "help just this once".

## When to use

Before executing a plan task, before any irreversible operation (delete, deploy,
publish, overwrite, spend), and at the start of any task whose ownership is
unclear. When a project defines a plan or contract, run this against it.

## What counts as a gate

- **Human-only work** — a task explicitly reserved for a human (e.g. tagged
  `human_only`). The agent prints the task and halts; it does not execute,
  assist, summarize, derive, or solve it.
- **Human gates** — an approval checkpoint (e.g. `human_gate`, a publication
  review, a pending entry in a `human_gates_pending` list). Blocking until a
  human explicitly clears it — across restarts.
- **Hard checkpoints** — a task whose failure must abort the larger unit of
  work rather than be worked around.
- **Irreversible actions** — anything that cannot be cleanly undone, even if no
  explicit gate is declared. Treat as a gate by default.

## Procedure

1. **Identify the action** and the unit of work it belongs to.
2. **Read the contract** — the project's plan, `AGENTS.md`/`CLAUDE.md`, and any
   state file listing pending gates. Gates declared there are authoritative.
3. **Classify** — is the action gated? When genuinely unsure, treat it as
   gated. The cost of a false halt is a question; the cost of a false proceed
   can be unrecoverable.
4. **If gated → halt protocol:**
   - Print clearly: *what* is gated, *which* gate, and *what a human must do*
     to clear it.
   - Record that the gate was reached (see [[run-log]]).
   - Stop. Do not start adjacent un-gated work that presumes the gate passed.
5. **If not gated** → proceed, but log the action.

## Rules

- A gate does not bend. There is no "just this once" exception.
- Never silently clear a gate. A gate is cleared only by explicit human action.
- A pending gate survives restarts — re-check the state file every session
  (see [[resume-state]]).
