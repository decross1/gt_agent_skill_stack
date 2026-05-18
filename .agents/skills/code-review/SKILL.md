---
name: code-review
description: Review code changes before they merge. Use after implementing a change and before opening or landing a PR — checks correctness, scope, tests, and research-specific risks like silent metric changes or data leakage.
---

# code-review

A pre-merge review pass. Read the diff as an adversary: assume it is wrong and
look for the proof.

## When to use

After a change is implemented, before [[ship]]. Also usable to review someone
else's diff.

## Checklist

**Scope**
- Does the diff do exactly what was asked — no more, no less?
- Unrelated changes, debug prints, commented-out code, stray files?

**Correctness**
- Walk the changed logic by hand on one real input.
- Edge cases: empty input, single element, NaN/inf, off-by-one, the boundary
  of every new branch.
- Error handling: failures surfaced, not swallowed.

**Tests**
- Is there a test that fails without this change and passes with it?
- For bug fixes, a regression test reproducing the original bug.

**Research-specific risks**
- Does any change touch metric computation, evaluation, or data splits? If so,
  flag it loudly — these change results silently.
- Train/eval leakage: shared rows, leaked features, fitting on test data.
- Hard-coded seeds, paths, or hyperparameters that should be config.
- Numerical: dtype changes, precision loss, unstable ops.

**Maintainability**
- Names say what they mean; matches surrounding style.
- No duplicated logic that should be shared.

## Output

Group findings as **blocking** (must fix before merge), **non-blocking**
(should fix), and **nits** (optional). For each blocking finding, name the file,
line, and the fix. If nothing is blocking, say so plainly.
