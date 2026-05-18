---
name: validate
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
  the authority to re-band it.
- **Mismatches are reported, never recoded.** If reality disagrees with the
  expected signal, report the disagreement. Do not edit the expectation to fit.

## Procedure

1. **Enumerate** every criterion as a separate check.
2. For each: state the **expected** signal, run the check, record the
   **observed** result, and a verdict — `pass` / `fail` / `inconclusive`.
3. An inconclusive check is not a pass — say what is needed to resolve it.
4. **Overall verdict**: pass only if every required check passed. One required
   fail → the whole validation fails.

## Output

A per-check table (criterion → expected → observed → verdict) and the overall
verdict, stated plainly. Record the result via [[run-log]]. If a check fails on
something broken rather than merely unmet, hand off to [[investigate]].

## Rule

If you are tempted to explain why a fail "should really count as a pass", that
is the moment to stop and report it as a fail.
