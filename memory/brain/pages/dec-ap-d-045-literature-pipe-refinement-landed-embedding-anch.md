---
slug: "dec-ap-d-045-literature-pipe-refinement-landed-embedding-anch"
type: "decision"
date: "2026-06-09"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-045 — Literature-pipe refinement landed: embedding anchors FALSIFIED as off-domain separators; R0 LLM-topicality gate + two-axis novelty + critic hardening; bar honestly NOT met, residuals characterized

_apparatus decision_

**Date locked.** 2026-06-09 (evening session; workflow `wf_3fc91fc6-0de` + serial
integration). References P-009 ("calibrate a discriminative gate against a varied set,
not a single instance") and the iteration-068 external review.

**The negative result (the load-bearing finding).** Both corpus-derived semantic-anchor
variants were falsified as off-domain separators on a 22-case labelled set + ~45
historical hypotheses, by the procedural rule declared BEFORE calibration: global
foundational-centroid cosine separation gap **−0.079**, per-collection max-cosine
**−0.075** (required: ≥ +0.05). Mechanism: a genuinely novel on-domain hypothesis is far
from the existing corpus BY DEFINITION of novelty — the same place a
vocabulary-camouflaged off-domain hypothesis sits. Distance-to-known-content structurally
conflates the two. `ANCHOR_LOW`/`ANCHOR_BORDERLINE`/`SPREAD_MAX` ship as None (rules
R3/R4/R5 inert); `run_state/domain_anchor.json` + `calibrate_anchor.py` remain as the
measurement apparatus.

**What shipped instead (single rule-7 revision cycle).** R0: an explicit LLM topicality
judgment (`orchestrator/topicality.py`, condemns ONLY on literal "off", fail-open to
None), wired at both nara relevance sites and the battery; the two-axis novelty rubric
(`novelty_axes` = phenomenon × substrate × predicted_direction, deterministic legacy-class
mapping, `docs/novelty_two_axis_rubric.md` pre-registered); critic hardening (`undecidable`
fails closed everywhere: schema_mismatch/timeout fallbacks, coverage-adequacy bar,
low-confidence override, the nara placeholder, the skeptic demotion — raw verdicts kept in
`verdict_overridden_from`); corpus de-drift (default retrieval = foundational +
papers_recent; `ml_intern_fetched` opt-in via the escalation path, D-038 preserved);
targeted ingest of 8 LLM-agent GT papers closing the 068 corpus gap.

**Battery outcome (bar NOT met — reported, not coerced; revision cap reached).**
Locked bar ≥0.80 acc ∧ recall 1.0 ∧ 0 ungated: **FAILED** at 0.636 / 0.875 / 1.
Versus the morning baseline (0.50 / 0.0 / recurring bug): R0 caught 7/8 off-domain
(all camouflaged + drift probes); every gated case tempered end-to-end
(`unclear`/`undecidable`); the survives→skeptic→survives path passed on a true novel
(canary_on_03). **Live-pipe proof:** the original FASE bug class now resolves honestly
(iter-2026-06-09-007: R0, unclear/undecidable, low_confidence=true) and the 068 p-beauty
re-run moved to **rediscovery/restated** with axes {known, unstudied_llm, matches} —
exactly the review's predicted correction.

**Residuals (named, for the next session — no further tuning this session):**
1. Domain-BOUNDARY claims (LLM-behavior with GT framing, fase_off_01) pass topicality —
   needs a finer domain definition or a skeptic-side off-domain attack, not threshold
   tuning. The one remaining ungated novel/survives.
2. Restatement recognition on plain-language phrasings still weak (4 rediscoveries →
   survives/undecidable); the named escalation is routing restatement through the Qwen
   skeptic (D-044 infrastructure is in place).
3. The critic still retreats to `undecidable` on 2/3 corpus-silent novels despite the
   STEP-3 instruction (prompt adherence is stochastic; promotion-path starvation risk).
4. `predicted_direction=deviates` over-assignment inflates `novel` via the
   known+deviates→novel mapping (falsifiable_01/02, pbeauty battery phrasing).
5. R0 over-gates ~3 on-domain cases incl. nonsense rows (epistemically harmless but
   costs battery accuracy).

**Reversibility.** All additive: R0 fail-open, anchor rules inert, overrides carry
provenance, schema changes additive. The battery + calibration artifacts under
`experiments/lit_falsification_battery/runs/` are the regression baseline.
