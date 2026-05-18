---
name: repro-check
description: Verify a result is reproducible before it is trusted or shipped. Use before adopting an experiment outcome, citing a number, or merging a results-changing diff — checks seeds, data versions, environment pinning, and run-to-run variance.
---

# repro-check

A result is not a result until it reproduces. This skill is the gate between
"the run finished" and "we believe the number".

## When to use

Before adopting an experiment's verdict, before quoting a metric in a PR or
report, and as part of [[code-review]] when a diff changes results.

## Checks

1. **Seed control** — Are all sources of randomness seeded (framework, data
   shuffling, augmentation, init)? Is the seed recorded in the
   [[experiment]] entry?

2. **Data version** — Is the dataset, split, and preprocessing pinned to a
   version or hash? Could the data have changed under the run?

3. **Environment** — Are dependencies pinned? Would a fresh environment produce
   the same result? Note hardware-dependent nondeterminism (e.g. some GPU ops).

4. **Code provenance** — Was the run made from a clean, committed tree? Does the
   logged commit actually match?

5. **Variance** — Run the key result ≥2–3 times with different seeds. Report
   mean and spread. A claimed improvement smaller than the seed-to-seed spread
   is not yet a real improvement.

6. **Independence** — Could the result be a leak (train/eval overlap), an eval
   on data the model saw, or a metric bug? Re-confirm the baseline was measured
   the same way.

## Output

A pass/fail per check with evidence. State plainly whether the result is
**trustworthy**, **trustworthy with caveats** (list them), or **not yet
established** (say what run is still needed). Record the conclusion in the
[[experiment]] entry's verdict.
