---
slug: "runlog-instrumentation-block1-via-dynamic-workflow-l975"
type: "run_log_entry"
date: "2026-06-06"
source: "week1.run.jsonl:975"
---

# a_bgt_rsi: Nara — week1.run L975

_every run mode emits active_run + real inference internals + run_id, UI-readable, atomic, DATA_SHAPES updated_

**Did:** workflow wf_93cc6fa0-b39: active_run.json (all run modes, atomic) + per-call worker_activity.jsonl (real tok/s, synthetic:false) + run_id contextvar on calls + exp orchestrator-rows; suite 642->664; real smoke confirmed active_run lifecycle…

**Observed:** status=passed day= duration_ms=720328 fallback=None
