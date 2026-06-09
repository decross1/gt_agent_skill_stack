---
slug: "runlog-exp008-first-live-run-triage-l1001"
type: "run_log_entry"
date: "2026-06-08"
source: "week1.run.jsonl:1001"
---

# a_bgt_rsi: Nara — week1.run L1001

_a real H0/H1 once arm C actually serves; no false verdict from infra failure_

**Did:** first live arm-C run: :8002 OOM'd at startup (GB10 128GB unified; prod gemma 50GB + qwen 28GB resident, no --gpu-mem cap on arm C -> vLLM grabbed ~90%). ALL 10 qat novelty calls = APIConnectionError (agreement 0.0 is a CRASH ARTIFACT, not a…

**Observed:** status=observed day= duration_ms=None fallback=None
