---
slug: "runlog-2026-06-10-workstream-a-provenance-emit-l1217"
type: "run_log_entry"
date: "2026-06-10"
source: "week1.run.jsonl:1217"
---

# a_bgt_rsi: Nara — week1.run L1217

_every LLM call attributable to (run, role, backend, model); no silent unregistered work; targeted tests green_

**Did:** backend field on all 4 call-record producers + calls schema; worker_activity backend/model + call_async/nara/subagent emission; subagent run_id + start/finish events; nara set_run_id leak fixed (wrapper extraction, 3 regression tests green)…

**Observed:** status=passed day= duration_ms=4500000 fallback=None
