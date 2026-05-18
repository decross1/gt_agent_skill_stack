---
name: resume-state
description: Resume a plan-driven project from its state file. Use at the start of a session on a project that executes a written plan task-by-task — reads the plan and state file, finds the first incomplete task, honors pending gates, and briefs before continuing.
---

# resume-state

Pick up a plan-driven project exactly where it was left, with no guessing and no
re-running of finished work. This is the start-of-session ritual for any project
whose work is governed by a written plan and a state file.

## When to use

First action of a session on a project that has an authoritative plan (e.g.
`plan.yaml`) and a state file tracking progress. For projects without a formal
plan, use [[context-restore]] instead.

## Procedure

1. **Read the contract first.** The project's `AGENTS.md`/`CLAUDE.md` and the
   plan's preamble — before parsing any task. The contract defines what the
   agent may and may not do.

2. **Read the state file.** It is authoritative on resume. Identify:
   - the current unit of work (e.g. `current_day`),
   - `completed_tasks` — these are **not** re-run,
   - any pending human gates — these are **blocking** (see [[gate-check]]),
   - any aborted units and recorded fallbacks.

3. **Find the resume point** — the first incomplete task in the current unit.
   Do not skip ahead; do not restart earlier units.

4. **Honor gates before anything else.** If a gate is pending, halt at it now —
   do not begin work that presumes it cleared.

5. **Reconcile with reality.** Verify the state file against the actual repo and
   environment (`git status`, files, services). If they disagree, the
   discrepancy is the first thing to surface — do not blindly trust either;
   investigate.

6. **Cross-check the run log.** The fine-grained [[run-log]] should be
   consistent with the state file. A task in the log but not the state file (or
   vice versa) is a discrepancy to report.

## Output

A short briefing before doing any work: current unit, the resume task, any
blocking gate, and any state/reality discrepancy. Then either halt at a gate or
proceed to the resume task. Every executed task is logged via [[run-log]].

## Rule

The state file is authoritative — but it is a record, not reality. When the two
disagree, surface it; never paper over it to keep moving.
