---
name: ship
layer: B
runtime-safe: false
description: Take a finished change from working code to a merged or PR-ready state. Use after review passes — runs tests, sanity-checks the diff, writes the commit/PR message, and records the decision.
---

# ship

The last mile: turn a reviewed change into something landed cleanly. This skill
is mechanical on purpose — the thinking happened in [[plan-research]],
[[investigate]], and [[code-review]].

## When to use

After [[code-review]] reports nothing blocking. Not before.

## Procedure

1. **Verify clean state** — Confirm the working tree contains only intended
   changes (`git status`, `git diff`). No stray files, no debug output.

2. **Run the full test suite** — Use the project's own command. All tests must
   pass. If any fail, stop and hand back to [[investigate]] — do not ship red.

3. **Re-run any affected experiment** — If the change touches results, the
   relevant run is current and logged (see [[experiment]]).

4. **Write the commit message** — Imperative subject line; body explains *why*,
   not what the diff already shows. Reference the experiment or issue.

5. **Open / update the PR** — Description states: what changed, why, how it was
   tested, and any result deltas. Link the plan and experiment log.

6. **Record the decision** — Append the outcome to `memory/DECISIONS.md` with
   the date.

## Rules

- Never ship with failing or skipped-to-hide tests.
- Never bundle an unrelated change "while I'm here" — separate PR.
- If the change is irreversible (data migration, deleted artifacts), say so
  explicitly in the PR and get confirmation before landing.
