---
slug: "dec-ap-d-003-serving-stack-vllm-with-moe-backend"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-003 — Serving stack: vLLM with `--moe-backend marlin`

_apparatus decision_

**Date locked.** April 2026 with vLLM 0.19 release.
**Decision.** vLLM ≥ 0.19, image `vllm/vllm-openai:gemma4-cu130`, launched
with `--moe-backend marlin` and the FLASHINFER_CUTLASS NVFP4 linear
backend.
**Alternatives.**
- Ollama (Q4_K_M GGUF, gemma4:26b).
- SGLang.
- Custom inference loop.
**Rationale.** vLLM 0.19+ shipped the SM121 NVFP4 fixes broken since
March; Ollama is faster for single-stream but slower for concurrent
batching and weaker on continuous-batching semantics that the loop will
use heavily. vLLM gives an OpenAI-compatible endpoint, which keeps the
wrapper layer thin. SGLang would also work but vLLM has more community
mileage on this exact stack.
**Operational pin.** Image tag `:gemma4-cu130` is NOT a superset of
`:gemma4` (the latter is the dev image and crashes on FP4 GEMM). Capture
the image digest at first boot and pin the digest, not just the tag.
**Reversibility.** Easy at the serving level (any OpenAI-compatible
endpoint can substitute). Hard at the version level — downgrading vLLM
below 0.19 reintroduces the broken NVFP4 path on SM12x.

---
