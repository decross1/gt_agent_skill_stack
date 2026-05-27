---
slug: "runlog-day-4-day4-vllm-restart-for-tool-calling-l72"
type: "run_log_entry"
date: "2026-05-20"
source: "week1.run.jsonl:72"
---

# a_bgt_rsi: Nara — week1.run L72

_vLLM accepts tool_choice=auto without 400; MARLIN backend still used; MTP intact_

**Did:** setup/day4_vllm_serve_tools.sh — same image vllm/vllm-openai:v0.21.0, same NVFP4 weights, same MARLIN MoE backend, same MTP speculative_config (mtp method, num_speculative_tokens=4, draft model gemma-4-26b-a4b-it-assistant); adds --enable-a…

**Observed:** status=passed day=day_4 duration_ms=290000 fallback=None
