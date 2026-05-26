---
slug: "dec-ap-d-002-orchestrator-model-gemma-4-26b-a4b"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-002 — Orchestrator model: Gemma 4 26B-A4B MoE in NVFP4

_apparatus decision_

**Date locked.** April 2026, after Gemma 4 release.
**Decision.** Use `nvidia/Gemma-4-26B-A4B-NVFP4` (NVIDIA's official NVFP4
quantization, attention in BF16) as the orchestrator model on Spark.
**Alternatives.**
- Gemma 4 31B Dense — dense, slower on bandwidth-limited memory.
- Qwen 3.6 27B Dense — better coding (77.2 % SWE-bench vs. ~75 %); dense.
- Llama 4 / DeepSeek variants.
- `bg-digitalservices/Gemma-4-26B-A4B-it-NVFP4` — community quant with
  attention also in FP4.
**Rationale.** MoE wins on the Spark's 273 GB/s memory bandwidth: only
~3.8 B parameters activate per token. The 31B dense variant runs at ~4–7
tok/s (limited by reading all 31 B weights per token at 2 bytes each);
the 26B MoE achieves ~50 tok/s single-stream, ~115 tok/s aggregate at
three concurrent requests. Total parameter count is irrelevant; active
parameter count determines speed.
Independent confirmation: ai-muninn's April 13, 2026 run reports 52 tok/s
single-stream on Spark with vLLM 0.19+ and `--moe-backend marlin`.
NVIDIA's quant leaves self-attention in BF16 by design (modelopt default)
because quantizing attention to 4-bit hurts Gemma 4 accuracy more than
quantizing MLP does. This is a deliberate accuracy/size trade-off; the
NVIDIA checkpoint is correct for production.
**Reversibility.** Easy. Swap to Qwen 3.6 (D-006) or any vLLM-served
model is documented as a single config change.

---
