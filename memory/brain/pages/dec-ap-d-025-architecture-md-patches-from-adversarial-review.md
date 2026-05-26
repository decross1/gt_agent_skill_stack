---
slug: "dec-ap-d-025-architecture-md-patches-from-adversarial-review"
type: "decision"
date: "2026-05-20"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-025 — ARCHITECTURE.md patches from adversarial review

_apparatus decision_

**Date locked.** 2026-05-20
**Decision.** Apply the patches in
`notes/research/2026-05-19-adversarial-review/3a_architecture_md_patches.md`
to `ARCHITECTURE.md`: replace §6 with the labeled-Phase-1/Phase-2
version, insert §6.5 "Degradation metrics," add the active-vs-passive
paragraph to §4.4, add the compute-budgeting / critic / meta-review
paragraphs to §5.1, and add the two negative-scope bullets to §8.

Schedule the three additive run-log schema changes (P1
`human_intervention` event, P2 `retrieval_context` field on call records,
P3 `calibration_entry` event) as **Day 3.5** in `plan.yaml`, since they
amend Day-2 schema work that has already shipped. Day 3.5 is the
retroactive-amendment slot per the user's instruction that "amendments
to day 1, 2, or 3 go in as a new day 3.5."

**Alternatives.**
- Apply only the §6 changes and defer the rest. Rejected: §6.5
  degradation metrics and the §4.4 active-vs-passive paragraph are
  inseparable from the §6 Phase-2 additions (the meta-review worker
  closes the active-read gap in §4.4; the degradation metrics ride on
  the new annotations on steps 3/7/8).
- Don't apply; carry insights in supplementary memos only. Rejected for
  the same reason as the diagram patches — insights that aren't in the
  canonical architecture document effectively don't exist for any
  future reader.
- Treat P1/P2/P3 as Week-2 proposals and not touch Week 1 at all.
  Rejected by user direction: Day 3.5 captures the retroactive
  amendments to Days 1–3 cleanly, and P2's `retrieval_context` field
  is load-bearing on the project's reproducibility commitment which
  needs to be in place before Day 4 tool-call work hardens.

**Rationale.** Same source as D-024 — the architecture document is the
canonical written walkthrough of the apparatus; if Phase 2 additions
are not in it, they don't exist for any future reader. The Day 3.5
schema-work entries make the additive run-log changes traceable on the
same Week-1 cadence as the other days, and respect the inviolate rule
that version pins, human-only blocks, and hard checkpoints do not
change.

**Operational notes.** Six patches in
`3a_architecture_md_patches.md`; patch 6 was already folded into
patch 1, so five patches landed (1: §6 replacement; 2: §6.5 insert;
3: §5.1 additions; 4: §8 negative-scope bullets; 5: §4.4 active-vs-
passive paragraph). Day 3.5 added to `plan.yaml` with three
agent-executable tasks
(`day3_5_block2_retrieval_context_field`,
 `day3_5_block2_events_schema`,
 `day3_5_block2_wrapper_retrieval_passthrough`) and one human-only
prose task (`day3_5_block3_claudemd_prose`) — CLAUDE.md edits remain
the human's prerogative per the operating contract.

**Reversibility.** Easy. `git revert` the integration commit. The Day
3.5 plan.yaml entries are additive; they can be deleted without
affecting Days 1–7. The schema changes (when Day 3.5 executes) are
additive and nullable — older logs without the new field remain
valid.

---
