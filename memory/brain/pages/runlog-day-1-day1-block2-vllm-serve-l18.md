---
slug: "runlog-day-1-day1-block2-vllm-serve-l18"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:18"
---

# a_bgt_rsi: Nara — week1.run L18

_vLLM serving Gemma 4 NVFP4 with MARLIN; startup-log + curl assertions pass_

**Did:** vLLM EngineCore failed loading NVFP4 checkpoint — KeyError 'layers.0.experts.0.down_proj.input_scale' at gemma4.py:1359 load_weights. Pinned image vLLM 0.19.1.dev6 has no param slot for the per-expert NVFP4 input_scale tensors the nvidia/Ge…

**Observed:** status=failed day=day_1 duration_ms=0 fallback=None
