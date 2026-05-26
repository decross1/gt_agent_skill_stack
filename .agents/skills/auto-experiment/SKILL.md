---
name: auto-experiment
layer: B
runtime-safe: false
pack: research
description: Run an autonomous, unattended sequence of experiments under a fixed budget. Use for overnight tuning or search loops — repeatedly hypothesize, make one change, run within a per-run cap, keep-or-revert by the metric, and log every iteration, with explicit stopping conditions.
---

# auto-experiment

Run a search loop without a human in the seat. Each iteration proposes one
change, tests it, and keeps or reverts it by the numbers. The discipline here is
what makes an unattended run trustworthy rather than a pile of unexplained
diffs.

This is a **dev-time** skill — it drives an agent running an experiment loop. A
project's own runtime research loop is a separate system; see `BOUNDARY.md`.
For a single attended experiment, use [[experiment]] instead.

## When to use

A bounded autonomous search: hyperparameter/architecture tuning, prompt search,
overnight optimization — where the metric is automatic and many cheap
iterations beat one careful one.

## Before you start

1. **Gate-check the session.** Run [[gate-check]]. An unattended loop must not
   cross a human gate or take an irreversible action while no one is watching.
   If it would, it is not eligible to run autonomously.
2. **Pin the frame** (from [[plan-research]] or the task):
   - the **metric** and the direction of improvement,
   - **guardrail** metrics that must not regress,
   - the **per-run budget** (wall-clock or compute) and the **session budget**
     (total time, or a max iteration count),
   - the **off-limits set** — files, the evaluation harness, dependency list —
     that the loop may not touch.

## The loop

1. **Baseline.** The first run is the unmodified baseline. Nothing is judged
   until the baseline number exists. Log it via [[experiment]].
2. **Hypothesize.** Propose one change, with a reason it should move the metric.
   Prefer changes informed by what earlier iterations already showed.
3. **Apply one change.** Exactly one, so the result is attributable. Touch
   nothing in the off-limits set.
4. **Run within the per-run cap.** If a run exceeds its cap or crashes, treat it
   as a failed iteration (see [[fallback]] for capped switching) and revert.
5. **Measure.** Compute the metric and the guardrails.
6. **Keep or revert.** Keep the change only if the metric improves and no
   guardrail regresses; otherwise revert it cleanly so the next iteration starts
   from the current best. This keep/discard ratchet is the loop's memory.
7. **Apply the simplicity criterion.** All else equal, simpler wins. A tiny gain
   that adds hacky complexity is not kept; an equal-or-better result from
   *deleting* code always is.
8. **Log the iteration** — kept or reverted — as its own [[experiment]] entry
   and [[run-log]] line. Reverts are data, not noise.
9. **Repeat** until a stopping condition fires.

## Stopping conditions

Stop the whole session — do not loop forever — when any holds:

- the session budget (time or iteration count) is spent;
- no improvement over the current best for N consecutive iterations (declare N
  up front);
- repeated infrastructure failures (the loop is broken, not the model — hand to
  [[investigate]]);
- a guardrail breach or off-limits violation is detected.

## Resumability

An unattended run can be interrupted. Keep enough state — current best, iteration
count, budget spent — that the loop resumes from the last completed iteration
rather than restarting. See [[resume-state]].

## On finishing

- Run [[repro-check]] on the winning result before reporting it — an unverified
  autonomous result is a candidate, not a finding.
- Summarize: baseline → best result → the change(s) that produced it →
  iterations run, kept, reverted → budget spent.
- Record the outcome in `memory/DECISIONS.md`.

## Rules

- One change per iteration. Always revert to the current best on a non-win.
- Never exceed the budget; never touch the off-limits set; never add
  dependencies unless explicitly allowed.
- Every iteration is logged, including failures and reverts.
- The loop reports candidates. Adoption of a result is still a human call.
