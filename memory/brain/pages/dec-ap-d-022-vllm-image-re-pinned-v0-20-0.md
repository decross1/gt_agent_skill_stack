---
slug: "dec-ap-d-022-vllm-image-re-pinned-v0-20-0"
type: "decision"
date: "2026-05-19"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-022 — vLLM image re-pinned `:v0.20.0` → `:v0.21.0`; MTP enabled

_apparatus decision_

**Date locked.** 2026-05-19, Day-2 throughput resolution; human-attested
(decross1).
**Decision.** The inviolate vLLM image pin moves from
`vllm/vllm-openai:v0.20.0` to `vllm/vllm-openai:v0.21.0` — digest
`sha256:a230095847e93bd4df9888b33dab956fa9504537b828a23657d2b26fed57b5c9`,
vLLM 0.21.0, torch 2.11.0+cu130. MTP (Multi-Token Prediction)
speculative decoding is enabled on the Gemma 4 stack via
`--speculative-config '{"method":"mtp","model":".../gemma-4-26b-a4b-it-assistant","num_speculative_tokens":4}'`
paired with the staged official drafter. Supersedes the tag pinned in
D-020; resolves the MTP deferral in D-019.
**Alternatives.**
- Keep `:v0.20.0`, accept ~32 tok/s — rejected: the day_2 50-call
  sweep hard checkpoint requires aggregate ≥ 40 tok/s.
- Re-derive the 40 floor down to the GB10 structural baseline (R1) —
  rejected by the human in favor of meeting the floor.
- n-gram speculative decoding within v0.20.0 — rejected: workload-
  dependent, near-zero input/output overlap on the day_2 sweep
  prompts, would not reliably clear 40.
**Rationale.** Day-2's 50-call sweep failed check #3 (aggregate 29.75
tok/s vs the 40 floor). D-021 established decode is weight-bandwidth-
bound on GB10; the lever that clears the floor is speculative decoding,
which reads the target weights once per K tokens. Empirical image
introspection found `vllm/vllm-openai:v0.20.0` ships no `gemma4_mtp.py`
and no `Gemma4MTPModel` registry entry — PR #41745 (Gemma4 MTP, merged
2026-05-06 @ 27e0057) first appears in the **v0.21.0** release, which
bundles the merged fix (no `infra/vllm_patches/gemma4_mtp.py` bind-mount
needed). Measured: single-stream decode 32.21 → 69.44 tok/s (2.16×);
50-call sweep aggregate 29.75 → 56.09; all 5 sweep checks pass;
determinism intact (speculative decoding is lossless — the target
verifies every token). A DGX Spark community benchmark reached ~108
tok/s single-stream with the same config.
**Operational notes.** v0.21.0 keeps `--moe-backend marlin` (startup
log confirmed `Using 'MARLIN' NvFp4 MoE backend`), CUDA 13.0, torch
2.11.0+cu130, and the NVFP4 weights path — only the vLLM version moved.
The drafter MUST pair with the IT target (D-019; base target = 38%
slowdown). `--max-model-len` is set to 32768 (down from the 262144
default) to free unified memory for the drafter and stop host swapping
(folds in the E5 right-sizing). `infra/vllm_patches/gemma4_mtp.py` is
retired — kept in-tree only as a provenance record. The `day1_block2_*`
task bodies in `plan.yaml` retain `:v0.20.0` as the historical record
of what Day 1 ran. Launch script: `setup/day2_vllm_serve_mtp.sh`.
**Reversibility.** Easy — drop `--speculative-config` and the drafter
mount to fall back to the NVFP4 baseline; re-pin to a new digest after
verifying startup logs (per D-017).

---
