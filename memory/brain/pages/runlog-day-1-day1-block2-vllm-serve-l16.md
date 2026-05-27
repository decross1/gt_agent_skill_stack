---
slug: "runlog-day-1-day1-block2-vllm-serve-l16"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:16"
---

# a_bgt_rsi: Nara — week1.run L16

_vLLM serving with MARLIN MoE backend + MTP engaged; startup-log assertions pass_

**Did:** container exited(1) at MTP speculative-config step — pydantic ValidationError: drafter model_type 'gemma4_assistant' not recognized. Root cause: pinned image ships vllm 0.19.1.dev6 + transformers 5.5.0, predating merged PR #41745, which add…

**Observed:** status=failed day=day_1 duration_ms=0 fallback=None
