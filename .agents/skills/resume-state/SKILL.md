---
name: resume-state
layer: A
runtime-safe: true
pack: core
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

   **Special case — gate-armed periods.** If the run log shows a gate
   that was *armed* but has not yet cleared, the state file's
   `completed_tasks` may *lag* the run log. Pre-emptive gate-arming
   often means tasks continue to complete under the armed gate; they
   are observed in [[run-log]] but may not have been written through
   to the state file until the gate clears. When the two disagree
   across a gate-armed window, **treat the run log as canonical for
   the held period** and reconcile by walking it. Do not re-run
   completed work based on the lagging state. Surface the divergence;
   the project may also choose to write the state file forward
   (write-through after the gate clears) — but resume-state's
   recovery does not depend on that having happened.

6. **Cross-check the run log.** The fine-grained [[run-log]] should be
   consistent with the state file. A task in the log but not the state file (or
   vice versa) is a discrepancy to report.

7. **Surface active corrections.** Scan the project's decision log
   (`memory/DECISIONS.md` or the project's own) for the last few entries
   marked as **corrections** — durable rules the agent is expected to honor.
   A correction is a [[decision-log]] entry that names a rule of practice
   (not a one-off architecture pick); recognise it by an explicit
   `correction:` flag in the entry, or by a title that names a rule. Surface
   the last *N* unsuperseded corrections (default N=5; the project may set
   its own) in the briefing — by ID and one-line summary, not in full. If
   no decision log exists, note that and move on. The agent reads, it does
   not relocate or restate: authority remains in the decision log.

## Output

A short briefing before doing any work: current unit, the resume task, any
blocking gate, any state/reality discrepancy, and the *N* most recent active
corrections. Then either halt at a gate or proceed to the resume task. Every
executed task is logged via [[run-log]].

## Rule

The state file is authoritative — but it is a record, not reality. When the two
disagree, surface it; never paper over it to keep moving.
