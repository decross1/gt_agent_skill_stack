---
slug: "demo1-lit-falsification-real-run"
type: "reflection"
date: "2026-06-09"
source: "memory/brain/narratives.jsonl"
---

# demo1_lit_falsification_real_run

**Intent:** Answer the human's headline question with a labelled known-answer battery: does the literature pipe falsify with high accuracy, or need refinement?

**Did:** Ran the 13-case lit-falsification battery against live Gemma + the real ingested corpus; scored per-enum verdict accuracy, off-domain low-confidence-gate recall, and the FASE-class regression (ungated novel/survives).

**Observed:** Pipe FAILS the proposed bar: 50% verdict accuracy, gate recall 0/2 on off-domain, FASE-class survives recurs. Root causes (grounded in the cached retrievals): the retrieval_relevance gate is LEXICAL-OVERLAP-ONLY (fires at mean top-3 overlap <0.05) and is defeated by an off-domain hypothesis carrying GT vocabulary (fase_off_01 overlap 0.127) or by corpus drift to ML-arXiv papers (fase_off_02 overlap 0.193) -- it keys on surface vocabulary, not semantic topicality. The critic over-applies 'survives': 3/3 on-domain rediscoveries -> survives (not restated) even with correct retrieval; it only down-ranks on a DIRECT contradiction. POSITIVE: both falsifiable claims were correctly falsified -- falsification works on direct contradictions; the gap is restatement-detection + off-domain-tempering.

**Would do differently:** The 2026-06-09 lexical-overlap gate was calibrated on ONE bug instance (overlap 0.043) and is brittle -- calibrate gates against an adversarial/varied set, never a single instance. Next: add a SEMANTIC topicality signal (centroid cosine vs a GT-domain anchor, or a cheap LLM topicality check) alongside lexical overlap; give the critic explicit restatement-detection + an off-domain-temper rule; de-drift the corpus (constrain retrieve_literature to curated GT collections -- the ML-arXiv / day3_* pollution defeats the gate).

**Corrections honored:** inviolate-rule-4-no-coercion, mock-llm-discipline
