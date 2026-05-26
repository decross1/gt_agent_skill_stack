---
slug: "dec-ap-d-020-vllm-image-re-pinned-gemma4-cu130"
type: "decision"
date: "2026-05-18"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-020 — vLLM image re-pinned: `:gemma4-cu130` → `:v0.20.0`

_apparatus decision_

**Date locked.** 2026-05-18, Day-1 execution; human-authorized.
**Decision.** The inviolate vLLM image pin moves from
`vllm/vllm-openai:gemma4-cu130` to `vllm/vllm-openai:v0.20.0` — digest
`sha256:04563c302537a91aa49ebdfbceda96111c5712275999b7e8804fa598f0b5641d`,
vLLM 0.20.0, torch 2.11.0+cu130. Supersedes the image tag named in D-003.
**Alternatives.**
- Keep `:gemma4-cu130` — rejected: it cannot serve the checkpoint.
- Patch vLLM 0.19.1.dev6 inside the image — rejected: open-ended, fragile.
**Rationale.** `:gemma4-cu130` shipped vLLM `0.19.1.dev6`, whose
`gemma4.py` weight loader has no parameter for the per-expert NVFP4
`input_scale` tensors the `nvidia/Gemma-4-26B-A4B-NVFP4` checkpoint
ships — `KeyError: layers.0.experts.0.down_proj.input_scale` at engine
start. The checkpoint's own model card specifies `vllm/vllm-openai:v0.20.0`.
v0.20.0 serves it cleanly (MARLIN MoE backend confirmed; curl round-trip
returned `ok` in 1.45 s). `:gemma4-cu130` was a stale preview tag that
predated the published checkpoint — exactly the moving-tag risk D-017
flagged.
**Operational notes.** v0.20.0 also needs `--max-num-batched-tokens 8192`
(Gemma 4 is multimodal; vLLM force-disables chunked MM input, so the
batch-token budget must exceed `max_tokens_per_mm_item`=2496). The GB10
has no native FP4 compute (SM12x — D-018); vLLM uses the Marlin
weight-only FP4 path, so the plan's expected `FLASHINFER_CUTLASS for
NVFP4 GEMM` log line does not appear — `day1_block2_vllm_serve`
validation check #2 needs correcting to match.
**Reversibility.** Easy — re-pin to a new digest after verifying its
startup logs (per D-017).

---
