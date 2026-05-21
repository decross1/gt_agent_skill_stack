---
name: plan-research
layer: B
runtime-safe: false
description: Plan a research task with technical rigor before any code is written. Use when starting a new experiment, feature, model change, or investigation that needs a defensible design — produces a hypothesis, baseline, success metric, and the smallest experiment that could disprove it.
---

# plan-research

Produce a rigorous, falsifiable plan for a research-style task. The goal is not a
to-do list — it is a design that states what is being claimed, how it will be
tested, and what would prove it wrong.

## When to use

A new experiment, model/architecture change, data-pipeline change, or any task
where "did it work?" is non-trivial. Skip for mechanical edits.

This skill is for *designing* a plan. To *execute* an already-written plan
task-by-task from a state file, use [[resume-state]] instead.

## Procedure

Work through each section. Do not skip a section — instead, write "N/A — <reason>".

1. **Question** — One sentence. What specifically are we trying to learn or
   achieve? Distinguish a *capability* goal ("make X possible") from a
   *measurement* goal ("determine whether X helps").

2. **Hypothesis** — A falsifiable statement with a direction and, where possible,
   a magnitude. "Adding feature F raises metric M by ≥ Δ" beats "F should help".

3. **Baseline** — The exact thing the result is compared against: a commit, a
   config, a prior run ID, or a published number. No baseline → no claim.

4. **Success metric** — The primary metric, how it is computed, and the
   threshold that counts as success. Name secondary metrics and guardrail
   metrics (things that must *not* regress).

5. **Smallest experiment** — The cheapest run that could disprove the hypothesis.
   Prefer a fast, small-scale version before any expensive run. State the
   compute/time budget.

6. **Threats to validity** — List concretely: confounds, data leakage, an
   unfair baseline, seed/variance noise, overfitting to the eval set,
   metric gaming. For each, how it is controlled or why it is acceptable.

7. **Decision rule** — Written *before* running: "If M ≥ threshold and no
   guardrail regresses, we adopt; otherwise we revert and record why."

8. **Plan of record** — The ordered steps. Mark which are reversible and which
   are not.

## Output

Write the plan to the task thread. If the project keeps a planning log, append
it there. Record the resulting decision in `memory/DECISIONS.md` once the
experiment concludes. See also [[experiment]] for logging the run and
[[repro-check]] before trusting any result.
