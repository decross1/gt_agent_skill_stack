---
name: investigate
description: Systematically debug a failure, anomaly, or surprising result. Use when something is broken, a metric moved unexpectedly, a test fails intermittently, or a result looks too good or too bad — drives an evidence-based hypothesis tree instead of guess-and-check.
---

# investigate

A disciplined debugging method. The failure mode this prevents is *guess-and-patch*:
changing things until the symptom disappears without knowing why. Every step here
is about evidence.

## When to use

A bug, crash, failing or flaky test, a metric that moved without explanation, or
a result that is suspiciously good (often a leak or a metric bug) or bad.

## Procedure

1. **State the observation** — Precisely. What was expected, what happened, and
   the exact error / metric / output. Vague symptom → vague investigation.

2. **Reproduce deterministically** — Find the smallest, fastest, most reliable
   way to trigger it. Pin the seed, the data slice, the commit, the environment.
   If it cannot be reproduced, that is itself the first finding — pursue it.

3. **Establish a known-good and known-bad point** — A commit, config, or input
   where it works and one where it fails. Bisect the gap.

4. **Build a hypothesis tree** — List candidate causes, ordered by prior
   likelihood × cheapness to test. Do not pick a favorite yet.

5. **Test one hypothesis at a time** — Each test must be able to *eliminate* a
   branch. Record the result: confirmed / eliminated / inconclusive. Change one
   variable per test.

6. **Find root cause, not the nearest symptom** — Keep asking "why" until the
   answer is something you can fix or consciously accept. A fix you cannot
   explain is not a fix.

7. **Confirm** — Apply the fix, show the reproduction now passes, and show
   nothing adjacent regressed.

## Rigor rules

- No fix lands without a root-cause explanation.
- Every claim ("it's the data loader") cites the evidence that supports it.
- Suspiciously good results get the same scrutiny as failures — check for
  leakage, eval-set contamination, and metric bugs first.

## Output

Summarize: observation → root cause → evidence → fix → confirmation. Record
non-obvious root causes in `memory/DECISIONS.md` so the same trap is not
re-entered. See [[repro-check]] for reproducibility-specific failures.
