---
slug: "proposal-p-009"
type: "proposal"
date: "2026-06-09"
source: "memory/brain/proposals.jsonl"
---

# P-009 — A discriminative gate/threshold calibrated on a single observed failure instance is brittle — calibrate + regression-test against a varied/adversarial labelled set

_agent: primary-session/integrator_

**Verdict:** `open`

**Target:** brain → `gate-calibration-discipline`

**Change:** Add a brain methodology note: when adding a gate/threshold to catch an observed failure mode, do NOT calibrate it on that single instance. A gate tuned to one example over-fits the example's surface features and is defeated by a variant. Calibrate against a labelled set spanning the failure mode (including adversarial/camouflaged variants) and keep that set as a standing regression battery re-run whenever the gate changes.

**Reasoning:** 2026-06-09 a_bgt_rsi validation session, empirically demonstrated. The retrieval_relevance low-confidence gate (the 2026-06-09 critic-honesty fix) was calibrated on ONE bug instance (iter-2026-06-09-001, FASE off-domain, mean lexical overlap 0.043) with threshold 0.05. The lit-falsification battery (13 labelled cases, real Gemma) showed it is DEFEATED by an off-domain hypothesis phrased with on-domain vocabulary (fase_off_01 overlap 0.127) and by corpus drift (fase_off_02 retrieved ML-arXiv papers, overlap 0.193) -> gate recall 0/2 on off-domain, the FASE-class survives bug recurs. The gate keys on surface lexical overlap, not semantic topicality, because it was fit to a single instance. The battery is now the standing regression set; the apparatus fix (semantic topicality signal + critic restatement-detection + corpus de-drift) is tracked in a_bgt_rsi human/sessions/2026-06-09-validation.md. Generalizable beyond this gate: same risk for any single-instance-tuned validation threshold.

**References:** `demo1_lit_falsification_real_run`, `retrieval_relevance`, `iter-2026-06-09-001`, `a_bgt_rsi/experiments/lit_falsification_battery`, `a_bgt_rsi/human/sessions/2026-06-09-validation.md`
