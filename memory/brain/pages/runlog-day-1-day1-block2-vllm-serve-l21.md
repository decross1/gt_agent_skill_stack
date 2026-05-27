---
slug: "runlog-day-1-day1-block2-vllm-serve-l21"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:21"
---

# a_bgt_rsi: Nara — week1.run L21

_vLLM serving with MARLIN MoE backend; startup-log + curl assertions pass_

**Did:** vLLM v0.20.0 serving Gemma 4 26B NVFP4 — container Up, /health 200, curl /v1/chat/completions returned content 'ok' in 1.45s (HTTP 200, finish_reason stop). MoE backend = MARLIN confirmed (nvfp4.py:209, NOT CUTLASS_FP4). Image re-pinned (hu…

**Observed:** status=passed day=day_1 duration_ms=0 fallback=None

## Referenced by

- `harvest-h002-l11` (harvest_finding) — **observed_in**
