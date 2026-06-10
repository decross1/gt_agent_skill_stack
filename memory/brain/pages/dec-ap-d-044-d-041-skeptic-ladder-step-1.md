---
slug: "dec-ap-d-044-d-041-skeptic-ladder-step-1"
type: "decision"
date: "2026-06-09"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-044 — D-041 skeptic ladder step 1 VALIDATED: vllm-qwen is the standing independent skeptic; attack() seam shipped (default off)

_apparatus decision_

**Date locked.** 2026-06-09 (evening session). Executes the D-041 ladder; human-directed
("ship Qwen or whatever is the right skeptic this session — priority order Qwen →
Gemma-persona → Claude/Agent-SDK").

**Decision.** The independent-skeptic mechanism ships as
`orchestrator/novelty_skeptic.attack(hypothesis_text, iteration_id=None, backend=None)`:
its OWN retrieval (`query_top_k`, default curated collections — closes the
iteration-068 shared-neighbor blind spot), REFUTE-framed prompt, fail-closed parsing
(every failure path → `inconclusive`, never `survives_attack`). The critic hook
(`workers/critic_loop_v0._maybe_run_skeptic`) fires only on a final `survives` with a
clean gate, behind env `NARA_SKEPTIC` (default **off** until β); `refuted`/`inconclusive`
demote the verdict to `undecidable` with full observability
(`skeptic_verdict`, `verdict_overridden_from`).

**Backend.** Default resolves from `NARA_SKEPTIC_BACKEND`, default **`vllm-qwen`**
(`qwen3.6-27b-nvfp4-mtp` on `:8001`, max_tokens 3072 per the token-starvation
diagnosis). The D-041 stand-alone back-test PASSED 3/3 on the labelled battery subset:
falsifiable_01 (finite-PD cooperate-to-end) **refuted** citing
`osborne_rubinstein-chunk-850` (backward induction); falsifiable_02 (TFT dominant)
**refuted** citing `chunk-831` (strict dominance); novel_on_01 (true on-domain novel)
**survives_attack** with a correct no-prior-art rationale. Run-log entry
`skeptic_ladder_step1_live_test`.

**Alternatives.** (a) `ollama-coder` (the D-035 default) — DEMOTED: requires the
unset-by-default `OLLAMA_MODEL` env pin (fails closed as a silent-looking
`inconclusive`), and pages a SECOND qwen copy into the 121 GB unified pool alongside
the resident vllm-qwen container (observed thrash: 15-min hang). Still selectable
explicitly. (b) Gemma-4 adversarial persona (ladder step 2) — built and tested
(`GEMMA_ADVERSARY_PERSONA`, backend `vllm-gemma`), NOT validated live; remains the
operational fallback if vllm-qwen is down. (c) Claude via Agent SDK (step 3) —
design-only in `docs/skeptic_ladder.md` (~$0.04–0.055/attack, ≥3,600 attacks under the
$200 Max plan); wiring it is the D-014/ToS human decision, not taken.

**Reversibility.** Env-gated and additive; unset `NARA_SKEPTIC` to remove from the
pipe entirely. The D-041 β arming condition "validated independent skeptic" is now MET
at ladder step 1; the memory-guard prerequisite stands unchanged.

---
