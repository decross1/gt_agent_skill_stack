---
name: validate
layer: A
runtime-safe: true
pack: core
description: Run a validation as a set of independent pass/fail checks. Use when a task or experiment defines explicit success criteria — checks each signal separately, reports pass or fail honestly, and never coerces a near-miss into a pass.
---

# validate

Check work against its declared success criteria — honestly. The failure mode
this prevents is the *silent coercion*: rounding a near-miss up to a pass,
merging two checks so a weak one hides behind a strong one, or downgrading a
failure to "informational" without authority.

## When to use

Whenever a task, experiment, or plan step has explicit acceptance criteria —
"Validation:" bullets, a `pass_signal`/`fail_signal`, a metric band, an expected
output. Run this before declaring the work done.

## Principles

- **Each criterion is its own check.** If the source lists three validation
  bullets, that is three checks with three independent verdicts. Do not collapse
  them.
- **The signal is defined in advance.** Compare the observed result against the
  *declared* pass condition, not against a feeling that it is close enough.
- **A near-miss is a fail.** "Below the band but close" is a failure unless the
  source itself explicitly bands that range as informational. You do not have
  the authority to re-band it. (If the *criterion itself* is wrong — not the
  result — see "When the criterion itself is wrong" below.)
- **Mismatches are reported, never recoded.** If reality disagrees with the
  expected signal, report the disagreement. Do not edit the expectation to fit.

## When the criterion itself is wrong

The principles above assume the declared criterion is correct and only the
result is in question. Sometimes the **criterion** is the thing that is wrong —
a threshold no correct run could reach, a string that encodes a false
assumption, a check that is literally unsatisfiable. That is not licence to
coerce; it is a different finding, with its own protocol:

1. **Do not coerce, do not silently substitute.** You still may not re-band a
   result to `pass`, and you may not quietly swap in your own check and call
   that the criterion. Either erases the disagreement.
2. **Verify the underlying intent — separately.** Work out what the criterion
   was *trying* to establish and check that on its own terms. Report it as its
   own observation, labelled a substitute — not as the criterion.
3. **Report the criterion as mis-specified**, with the evidence (e.g. "no chunk
   size reaches the 0.85 bar"; "the >=30 threshold is unreachable by the
   prescribed task scope").
4. **Escalate — do not self-amend.** A mis-specified criterion is fixed by
   whoever owns the plan and recorded as a decision (see [[decision-log]]). The
   validator surfaces it; it does not rewrite the contract.

The check's verdict here is **not `pass`** — it is `fail` or `inconclusive`
with the mis-specified-criterion finding attached, pending the amendment.

## Procedure

1. **Enumerate** every criterion as a separate check.
2. For each: state the **expected** signal, run the check, record the
   **observed** result, and a verdict — `pass` / `fail` / `inconclusive`.
3. An inconclusive check is not a pass — say what is needed to resolve it.
4. **Overall verdict**: `pass` only if every required check passed; one
   required `fail` → the whole validation fails. `partial_pass` is allowed in
   one narrow case only — every check the agent controls passed and the sole
   non-passing check is a mis-specified criterion, reported and escalated per
   "When the criterion itself is wrong". It is never a softer word for a
   validation that actually failed.

## Output

A per-check table (criterion → expected → observed → verdict) and the overall
verdict, stated plainly. Record the result via [[run-log]]. If a check fails on
something broken rather than merely unmet, hand off to [[investigate]].

## Rule

If you are tempted to explain why a fail "should really count as a pass", that
is the moment to stop and report it as a fail.
