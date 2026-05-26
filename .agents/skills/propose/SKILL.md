---
name: propose
layer: B
runtime-safe: false
pack: brain
description: File a proposal to improve a brain page, an active rule, or a skill. Use when an agent has identified an improvement worth durable consideration — not a one-off comment. Appends to `memory/brain/proposals.jsonl`; review is the [[review-proposal]] skill's job, not yours.
---

# propose

Capture an idea for improvement as a durable, reviewable record. The point is
*not* to assert the change is right — the point is to surface it so it can be
weighed against active rules and accepted, rejected, or routed to a human.

Proposals are the brain's way of evolving without an agent silently editing
things it should not be editing. A proposal is a *request*; [[review-proposal]]
decides.

## When to use

When during a task — or in reflection after one — the agent identifies a
*specific, durable* improvement: a brain page that is stale or wrong, an
active rule that no longer applies, a skill section that mis-fits real use.
Skip `propose` for one-off comments (those go in [[narrate]]'s
`would_do_differently` field) or for trivial fixes inside the agent's own
work (those are part of the task itself).

Pairs with [[narrate]] (a reflection that ends with a proposal references
the proposal id), [[decision-log]] (an *accepted* proposal that changes a
rule materializes as a new `correction:`-flagged decision), and
[[review-proposal]] (the next step in the loop).

## Entry shape

Append one JSON object per line to `memory/brain/proposals.jsonl`:

```json
{
  "timestamp": "<ISO 8601>",
  "proposal_id": "<P-NNN, sequential>",
  "agent_id": "<who filed it>",
  "title": "<short imperative — what would change>",
  "target_type": "page | rule | skill | edge | other",
  "target": "<slug of the brain page, rule id (FR-NNN/AR-NNN), or skill name>",
  "change": "<concrete description of the proposed change>",
  "reasoning": "<why this is worth changing; what triggered the proposal>",
  "references": ["<task_id, brain page slug, or decision id this depends on>"],
  "status": "open"
}
```

Outcome entries (accept / reject / human-review) are *new* entries appended
by [[review-proposal]], not edits of this one.

## Procedure

1. **Locate the target.** If you cannot name a concrete `target` (a page
   slug, a rule id, a skill name), the proposal is not ready — sharpen it
   first. A vague proposal is rejected by [[review-proposal]] on principle.
2. **Cite the rules.** If the proposal *changes* an active rule, name the
   rule's id (FR-NNN / AR-NNN from `memory/brain/rules.md`). If the proposal
   *complies with* a rule but extends it, say so. Proposals that ignore the
   active rules are auto-rejected.
3. **State the change concretely.** "Improve the X skill" is not a change.
   "Add a 'when to extend the enum' subsection to run-log's Status values"
   is.
4. **Append** to `memory/brain/proposals.jsonl`.
5. **Stop.** Do not also implement the change. The proposal-review loop
   exists exactly so that propose and decide are different steps.

## Rules

- **Append-only.** A proposal that needs revising is *re-filed* as a new
  entry that references the prior `proposal_id`.
- **One proposal, one change.** Bundling N changes makes the verdict
  ambiguous. Split.
- **Filing is not enacting.** A proposal does not change anything until
  [[review-proposal]] accepts it and the source-of-truth file
  (DECISIONS.md / SKILL.md / brain page) is updated.
- **Do not propose secrets or destructive operations.** Proposals are
  durable; review is the place to halt at irreversibility, not propose.

## Pairing

[[review-proposal]] reads the open proposals and decides. The active rules
live in `memory/brain/rules.md` (regenerated from
`memory/DECISIONS.md`'s correction entries by `scripts/regen_rules.py`).
Accepted rule changes pass through [[decision-log]] to become new
canonical corrections.
