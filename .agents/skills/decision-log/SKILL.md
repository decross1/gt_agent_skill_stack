---
name: decision-log
layer: C
runtime-safe: false
description: Record a durable decision so its reasoning survives. Use when a non-obvious, hard-to-reverse, or contested choice is made — captures the decision, the alternatives considered, the rationale, the reversibility, and any supersedes-link as one append-only dated entry.
---

# decision-log

Write a decision down so that months later — or a different agent — can ask
"why did we pick this?" and get an answer without re-deriving it. The failure
mode this prevents is the *unrecorded choice*: a decision that looks arbitrary
or wrong later because the alternatives and the reasoning were never captured.

## When to use

When a **durable, non-obvious choice** is made — an architecture or tooling
choice, a pin (version, dependency, dataset), a scope cut, a fork between
approaches, or a correction of an earlier decision. Skip it for routine,
obvious, or trivially reversible choices — those are noise in the log.

Pairs with [[plan-research]] (a plan's decision rule becomes a logged decision
once resolved) and [[investigate]] (a non-obvious root cause is a decision
about what is true).

## The entry

Append one entry to the project's decision log (`memory/DECISIONS.md`, or the
project's own). Every entry carries, at minimum:

- **Date** — when the decision was locked in.
- **Title** — short and ID-able, so other docs can cite it.
- **Decision** — what was chosen, stated plainly.
- **Alternatives** — the options *not* taken. A decision with no alternatives
  listed is not a decision — it is a default no one examined.
- **Rationale** — why this option beat the alternatives; tie it to evidence
  where there is any.
- **Reversibility** — how hard this is to undo (trivial / easy / medium /
  hard) and what undoing it would cost. This is what a future reader most
  needs and can least reconstruct.
- **Supersedes** — the earlier decision this replaces, by ID or date, or
  "none".

## Rules

- **Append-only.** Never rewrite or delete a past entry. A decision that turns
  out wrong is corrected by a *new* entry that supersedes it — the wrong one
  stays, as the record of what was believed and when.
- **Maintain the supersedes-chain.** When a decision is revised more than once,
  each entry names the one directly before it, so the chain is walkable.
- **A dated in-place update is allowed** — appending a `YYYY-MM-DD update:`
  note *within* an entry as it evolves — because it adds, it does not rewrite.
- **Alternatives and reversibility are not optional.** They are the two fields
  a future reader cannot reconstruct; an entry missing either is incomplete.

## Pairing

The fine-grained execution trace is [[run-log]]; the transient session handoff
is [[context-save]]. `decision-log` is the durable middle layer — the *why*
behind the *what*, kept for the life of the project.
