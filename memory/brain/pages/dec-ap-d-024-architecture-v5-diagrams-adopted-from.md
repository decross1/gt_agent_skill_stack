---
slug: "dec-ap-d-024-architecture-v5-diagrams-adopted-from"
type: "decision"
date: "2026-05-20"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-024 — Architecture v5 diagrams adopted from adversarial review

_apparatus decision_

**Date locked.** 2026-05-20
**Decision.** Adopt `docs/diagrams/architecture_v5.svg` and
`docs/diagrams/intelligence_loop_v5.svg` as the canonical diagrams. The
v4 diagrams are kept in `docs/diagrams/` per the versioning convention
(`docs/diagrams/README.md`).

**v5 changes (loop diagram).**
- Critic / red-team node inserted between Step 2 (generate) and Step 3
  (experiment); retry edge bounded at ≤ 2 cycles. Phase 2.
- Meta-review synthesis node inserted between Step 1 (literature scan)
  and Step 2 (generate). Phase 2.
- Experiment-outcome → loop-memory feedback edge added, gated by Step 8
  (human review). Phase 2.
- Step 6 (novelty evaluation) annotated with Phase 1 human-sampling
  requirement and Phase 2 generator-scorer separation + structured-
  claim search.
- Step 7 (log) annotated with `retrieval_context` reproducibility field
  (schema work scheduled as Day 3.5).
- Step 3 (experiment) annotated with per-hypothesis compute budget
  (Phase 2).
- Step 4 (robustness battery) annotated to clarify falsification ≠
  exploration.
- Degradation-metrics callout added on the right side
  (hypothesis:experiment ratio, model canary, retrieval-context audit,
  researcher calibration log).

**v5 changes (architecture diagram).**
- Orchestrator block expanded with Phase-2 annotation: compute budget,
  cost-aware bandit reward, critic + meta-review worker dispatch.
- `retrieval_context` reproducibility annotation under experiment logs.
- Phase-2 experiment-outcome feedback edge annotated (drawn fully in
  the loop diagram).

**Alternatives.**
- Leave v4 unchanged; capture additions in prose only. Rejected: the
  diagrams are referenced by both `ARCHITECTURE.md` and
  `PROJECT_CONTEXT.md` and are the first read for any new contributor;
  insights that don't make it onto the diagrams effectively don't
  exist.
- Redesign from scratch (v5 as full redraw). Rejected: the v5 deltas
  are additive and clearly labeled Phase 2; a full redraw would lose
  the clean separation between Phase 1 (in flight) and Phase 2
  (planned).

**Rationale.** The 2026-05-19 adversarial review (see
`notes/research/2026-05-19-adversarial-review/1_adversarial_review_memo.md`)
identified seven structural critiques of the Google AI co-scientist
that hold against this project's intended Phase 2 architecture. The v5
diagrams make the Phase 2 additions visible without redesigning Phase 1
elements that have already shipped or are mid-implementation.
v4 is preserved as a baseline showing the pre-review architecture.

**Operational notes.** `ARCHITECTURE.md` §6 reference updated to point
at `intelligence_loop_v5.svg`. `PROJECT_CONTEXT.md` and `START_HERE.md`
will be updated as a follow-up; the v4 SVGs remain present so existing
references do not break.

**Reversibility.** Trivial. Revert the `ARCHITECTURE.md` reference and
the `docs/diagrams/README.md` "current" pointer to v4. v5 files can be
moved to `docs/diagrams/retired/`.

---
