---
name: slip-ladder
layer: B
runtime-safe: false
pack: core
description: Declare a bounded sequence of deadline extensions when a task is on the right approach but not finishing inside its time budget. Use when [[fallback]] does not fit because there is no alternative approach to switch to — only "more time, same approach, with a stated cap". Each slip is logged; the cap is real; resolution criterion is declared upfront.
---

# slip-ladder

Handle the case where a task is *on the right track but slow*. Not every time
budget overrun is a fallback case — sometimes the approach is correct, the
metric is moving, and the right move is *more time*, capped and logged. The
failure mode this prevents is the **unbounded creep**: deadline slips with
no count, no reason recorded, no resolution criterion — until the project
quietly slides for weeks.

`slip-ladder` is the companion to [[fallback]]:

- **fallback** — "the primary approach failed or exceeded budget; switch to
  a different approach now". Different *method*, same task.
- **slip-ladder** — "the approach is right but the budget was wrong;
  extend, same method, capped slips, declared exit criterion".

Both are explicit, logged, and time-capped. The crime they share is
*pretending nothing happened*; the difference is what comes next.

## When to use

When **all of these** hold:

1. The current approach is producing signal in the right direction
   (metric moving toward the target; partial pass on a per-check basis).
2. No known *alternative approach* fits — [[fallback]] is not applicable.
3. More time would plausibly resolve it — not "we hope it works", but
   "the next step of *this* approach is well-defined".
4. The slip cost is acceptable to the wider plan (other gates / hard
   checkpoints still hold).

Skip slip-ladder when the metric is *not* moving, the cause is unknown
(use [[investigate]]), or the result has been re-derived multiple times
without convergence (escalate).

## The ladder

Declare upfront, before the first slip:

- **Cap.** Maximum number of slips before auto-escalation
  (typical: 2–4). The cap is a number, not a feeling.
- **Per-slip budget.** Time / iterations / token cost each slip is
  allowed. Same shape each rung; no implicit extensions.
- **Resolution criterion.** The signal that ends the ladder — same
  shape as a [[validate]] check (a metric crossing a threshold; a
  per-check verdict reaching pass). If the criterion is met inside
  any rung, `slip_resolved`. If the cap is hit without resolution,
  the next event is **escalation**, not another slip.
- **Diagnostic variant.** Often the *last* rung is a deliberately
  modified variant (smaller N, simpler prompt, different seed) used
  to diagnose, not just retry. Mark it as such in the slip's reason.

## Procedure

1. **Declare the ladder** in a single log entry: `slip_declared` with
   the cap, per-slip budget, resolution criterion, and the slip's reason.
   This is one entry; the slip itself is a separate `partial_pass` or
   `failed` task entry under the new budget.
2. **Run the slip** under the declared budget. Log the result like any
   other task ([[run-log]]) — same `task_id` family, slip number in the
   ID (e.g. `day7_1_block2_run_experiment` for the first slip of
   `day7_block2_run_experiment`).
3. **At the end of each rung, check the resolution criterion.**
   - If met → log `slip_resolved` with the resolving slip's task_id.
     The ladder is closed.
   - If not met AND slips < cap → log a new `slip_declared` with a
     refreshed reason and the new budget. Continue.
   - If not met AND slips >= cap → log `escalated` ([[run-log]]
     status) with the full ladder history. Do NOT silently add
     another rung.
4. **If the diagnostic variant was used as the resolving rung**, the
   `slip_resolved` entry names it explicitly — the result came from a
   *different* condition than the baseline run.

## Run-log status values

`slip-ladder` extends [[run-log]]'s default enum with:

- **`slip_declared`** — a new rung opened, with cap-so-far / cap-max,
  budget, criterion, reason.
- **`slip_resolved`** — the ladder closed by the resolution criterion;
  names the resolving entry.

(Same project-may-extend principle as [[run-log]]'s defaults.) If the cap
is exceeded, use `escalated`, not a new slip-status word.

## Rules

- **Cap before slips.** The first slip's log entry contains the cap. A
  slip without a cap declared *somewhere earlier* is a misuse — treat
  as escalation.
- **Each slip is its own logged event.** Do not bundle "slipped three
  times" into one entry. Each rung is auditable on its own.
- **Diagnostic rungs are tagged.** A diagnostic variant is not the
  same as a baseline retry; calling it one would silently change the
  experiment.
- **Cap-exceeded → escalate, never slip-again.** The ladder is the
  whole guard; extending past it removes the guard.
- **Honest naming.** "We slipped" is the entry; do not relabel as
  "completed" because the *next* run worked. The slip stays in the log.

## Pairing

[[fallback]] for the "different approach" case; [[run-log]] for the
status enum extension and append-only logging; [[validate]] for the
resolution-criterion shape; [[escalated]] (a [[run-log]] status) for
cap-exceeded handoff. A slipped result that ships still goes through
[[experiment]] / [[repro-check]] / [[ship]] — slipping does not change
the bar a result must meet, only how many tries were taken.
