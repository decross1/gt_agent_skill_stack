---
slug: "runlog-day-1-day1-block2-vllm-serve-l20"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:20"
---

# a_bgt_rsi: Nara — week1.run L20

_vLLM 0.20.0 serving Gemma 4 NVFP4 with MARLIN MoE backend; startup-log + curl assertions pass_

**Did:** human-authorized vLLM image re-pin: :gemma4-cu130 (vLLM 0.19.1.dev6) -> vllm/vllm-openai:v0.20.0, per the nvidia/Gemma-4-26B-A4B-NVFP4 model card. Re-attempting task #6 (baseline, no MTP) with the corrected image. day_1 abort to be lifted a…

**Observed:** status=started day=day_1 duration_ms=0 fallback=None
