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

2. **Run the full test suite** — Use the project's own command if it has a
   unified runner (`pytest`, `npm test`, …). If the project has no unified
   runner — tests are an enumerated per-unit set in its plan or docs — run
   exactly that enumerated set; "the suite" is that set, no broader, no
   narrower. All tests must pass. If any fail, stop and hand back to
   [[investigate]] — do not ship red.

3. **Re-run any affected experiment** — If the change touches results, the
   relevant run is current and logged (see [[experiment]]).

4. **Write the commit message** — Imperative subject line; body explains *why*,
   not what the diff already shows. Reference the experiment or issue.

5. **Integrate** — Use the project's own integration flow. The common shapes:
   - **PR-based** — open or update the PR; description states what changed,
     why, how it was tested, any result deltas; link the plan and experiment
     log.
   - **Commit-to-main** — push the clean commit directly; the commit message
     carries the same content a PR description would.
   - **Worktree-merge** — when the work ran in a parallel worktree under
     [[orchestrate]]'s worktree protocol, verify the file-boundary allow-list
     before integrating and merge with `--no-ff` so the integration is one
     reviewable commit.

6. **Record the decision** — Append the outcome to `memory/DECISIONS.md` with
   the date.

## Rules

- Never ship with failing or skipped-to-hide tests.
- Never bundle an unrelated change "while I'm here" — it is its own change,
  shipped separately.
- If the change is irreversible (data migration, deleted artifacts), say so
  explicitly in the integration message (PR description, commit body, or merge
  message) and get confirmation before landing.
