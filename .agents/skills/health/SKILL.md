---
name: health
layer: B
runtime-safe: false
description: Assess overall code and project health. Use for a periodic checkup or when a codebase feels like it is drifting — surveys tests, structure, dependencies, dead code, and reproducibility hygiene, then reports a prioritized snapshot.
---

# health

A whole-project checkup. Unlike [[code-review]] (one diff) this looks at the repo as a
whole and reports where the rot is.

## When to use

Periodically, when onboarding to a project, or when things feel slow/fragile and
you want a prioritized picture rather than a single fix.

## Survey

Gather evidence before judging. Run the project's own tooling where it exists.

1. **Tests** — Do they pass? How long do they take? Rough coverage of the core
   path. Any skipped/xfail tests, any flaky ones.
2. **Structure** — Oversized files/functions, tangled imports, unclear module
   boundaries, logic that belongs elsewhere.
3. **Dependencies** — Pinned? Outdated? Unused? Anything unmaintained.
4. **Dead code** — Unreachable branches, unused functions, stale configs,
   orphaned scripts and notebooks.
5. **Reproducibility hygiene** — Are seeds, data versions, and environments
   pinned and recorded? Are results traceable to a commit? (See [[repro-check]].)
6. **Docs & onboarding** — Is `AGENTS.md` accurate? Can a newcomer run it from
   the README alone?

## Output

A dashboard:

- **Status** per area: 🟢 healthy / 🟡 attention / 🔴 problem.
- **Top issues**, ranked by (impact × likelihood of biting soon).
- For each top issue: the evidence, and the smallest first step to fix it.

Do not fix things in this skill — report. Record systemic decisions in
`memory/DECISIONS.md`.
