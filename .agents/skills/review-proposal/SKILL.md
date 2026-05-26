---
name: review-proposal
layer: B
runtime-safe: false
pack: brain
description: Evaluate a [[propose]]'d proposal against active rules and route it to accept, reject, or human-review. Use when there are `open` entries in `memory/brain/proposals.jsonl`. Auto-rejects rule violations; auto-accepts trivial brain-content edits; everything else goes to human review.
---

# review-proposal

Decide what happens to a filed proposal. The point is to make the
brain's evolution *governed* — every accepted change is either trivially
aligned with active rules or has been deliberately approved by a human.
Nothing slips through.

## When to use

When `memory/brain/proposals.jsonl` contains one or more entries whose
`status` is `open` and no outcome entry supersedes them. May be invoked by
an agent (for auto-reject and trivially-aligned auto-accept) or by a human
(for the human-review path).

Pairs with [[propose]] (its input), `memory/brain/rules.md` (the active
rules used for auto-reject), and [[decision-log]] (an accepted *rule*
change materializes as a new `correction:` entry).

## Three verdicts

For each open proposal, choose exactly one:

1. **`auto-reject`** — the proposal violates an active rule in
   `memory/brain/rules.md` (FR-NNN / AR-NNN). Cite the rule id. The
   proposal is *not* implemented. The author may re-file a sharpened
   version.
2. **`auto-accept`** — the proposal is *trivially aligned* and *low-risk*:
   typo / formatting / dead-link fix on a brain page; backlinks
   regeneration; non-semantic content cleanup. **Auto-accept never
   touches: SKILL.md files, DECISIONS.md, active rules, the runtime-safe
   core, install.sh, BOUNDARY.md, edges that change graph lineage.** If
   any of those are touched, route to human-review.
3. **`human-review`** — everything else. The agent stages the change in
   the proposal entry and explicitly stops; the human picks it up.

## Entry shape (outcome)

Append one *new* JSON object per outcome to
`memory/brain/proposals.jsonl`:

```json
{
  "timestamp": "<ISO 8601>",
  "proposal_id": "<P-NNN — supersedes the open entry>",
  "supersedes_proposal_id": "<same P-NNN; explicit>",
  "agent_id": "<who reviewed — agent id, or 'human:<name>' for human review>",
  "verdict": "auto-reject | auto-accept | human-review | accepted | rejected",
  "verdict_reasoning": "<why; for auto-reject, cite the rule id>",
  "rule_cited": "<FR-NNN / AR-NNN, or null>",
  "decision_id": "<new DECISIONS.md head if the verdict spawned one, or null>",
  "status": "closed"
}
```

`human-review` is a *holding* outcome; the human later appends one more
entry with `verdict: accepted | rejected`. Both entries are kept; the chain
walks via `supersedes_proposal_id`.

## Procedure

1. **Load open proposals** — entries in `proposals.jsonl` whose `status` is
   `open` and not yet superseded.
2. **Load active rules** — `memory/brain/rules.md` (regen first with
   `scripts/regen_rules.py` if `memory/DECISIONS.md` has changed since the
   last `rules.md` mtime).
3. **For each proposal, in filing order:**
   a. If any active rule directly forbids the proposed change, **auto-reject**
      and cite the rule.
   b. Else if the change is in the auto-accept allowlist (brain-page content
      cleanup only — no SKILL.md, no DECISIONS.md, no rules, no boundary),
      **auto-accept** and update the targeted file.
   c. Else **human-review**.
4. **Materialize accepted *rule changes* through [[decision-log]]** — an
   accepted change to an active rule must produce a new DECISIONS.md
   entry with the `**Correction:**` flag and a `**Supersedes:**` link to
   the prior rule's source decision. `rules.md` regen picks it up
   automatically on next run.
5. **Append** outcome entries to `proposals.jsonl`.
6. **Stop at the boundary.** Auto-accepted changes that *would* touch
   SKILL.md / boundary / DECISIONS.md beyond a corrections-chain — even if
   they look trivial — are routed to human-review, no exceptions.

## Rules

- **Append-only.** Outcomes are new entries that supersede the open one,
  not edits.
- **Cite the rule on auto-reject.** A rejection without a rule-id is not a
  rejection; it is an opinion. Route to human-review instead.
- **The auto-accept allowlist is narrow on purpose.** It exists so the
  loop *moves* on trivia, not so it bypasses the rules. When in doubt,
  human-review.
- **One verdict, one outcome.** If a proposal needs splitting, route the
  original to human-review and ask the author to re-file as N proposals.

## Pairing

Filed by [[propose]]. Active rules from `memory/brain/rules.md` (regen by
`scripts/regen_rules.py`). Accepted rule changes flow through
[[decision-log]] to become new canonical corrections. The graph view
surfaces proposals so a human can see what is waiting.
