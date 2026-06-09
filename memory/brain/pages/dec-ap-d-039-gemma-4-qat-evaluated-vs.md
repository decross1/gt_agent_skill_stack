---
slug: "dec-ap-d-039-gemma-4-qat-evaluated-vs"
type: "decision"
date: "2026-06-08"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-039 — Gemma 4 QAT evaluated vs the NVFP4 pin (DRAFT, pending exp008 live run)

_apparatus decision_

**Status.** DRAFT — disposition PENDING the exp008 live run. Outcome: **[pending exp008 RESULTS.md]**.

**Date drafted.** 2026-06-08. Single-serial-integrator wiring of the `experiments/exp008_qat_eval/` benchmark harness (eval-only, no production swap).

**Trigger.** Gemma 4 QAT (quantization-aware training) is a quant variant of the *exact* model the orchestrator already runs (Gemma 4 26B-A4B). On GB10 the binding throughput constraint is memory bandwidth — fixed silicon (D-021). Bandwidth is not a lever we can pull, so the only thing a quant change can buy is **quality**, and quality is what determines whether the orchestrator's own judgments (novelty scoring, tool-calling, robustness) are trustworthy. QAT promises near-BF16 quality at 4-bit footprint, so it is worth measuring against the current NVFP4 pin — strictly as evaluation, not as a deployment.

**Design.** Three arms, eval-only, **NO production swap**:
- **Arm A** — the production NVFP4 pin as-is (`/mnt/models/gemma-4-26b-a4b-nvfp4`, `vllm/vllm-openai:v0.21.0`, Marlin MoE), the baseline.
- **Arm B** — Gemma 4 QAT as a llama.cpp GGUF quant.
- **Arm C** — Gemma 4 QAT unquantized under vLLM.

All arms are served on a **scratch container, port `:8002` only** (`serve_qat.sh`); the production `:8000` endpoint, image, config, and launch args are never touched. Eval calls log to `experiments/exp008_qat_eval/runs/*.jsonl`, never to production `logs/calls.jsonl`. Greedy decoding (temperature 0), one request at a time, for all quality runs. Eval surfaces: tool-calling, robustness, novelty.

**Planning-confirmed blocker.** Google ships **no vLLM-native W4A16 QAT** for the 26B-A4B variant — the MoE 4-bit path carries quality loss and only GGUF + unquantized weights exist. So even Arm B/C "winning" the eval does **not** yield a drop-in production swap: H1 (adopt QAT) is gated on a serving path that does not exist today. This experiment measures the quality ceiling; it cannot, by itself, authorize a swap.

**Tensions.** CLAUDE.md inviolate rule 2 (version pins are verbatim — the NVFP4 weights path + vLLM image + Marlin MoE backend); D-017/D-022 (the MTP-enabling image pin); D-018 (SM12.1 build constraints). This entry does not touch any of them — the harness is a scratch-port benchmark, and the pin stands.

**Reversibility.** The *experiment* is trivial and fully reversible (a scratch container + eval-scratch JSONL under `experiments/exp008_qat_eval/`; nothing in the serial spine, schema, agent_wrapper, workers, run_state, or production serving is touched). A *production swap*, by contrast, is **not** trivially reversible and is explicitly out of scope here — it would require its own decision once a real W4A16 serving path exists and the eval favors QAT.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
