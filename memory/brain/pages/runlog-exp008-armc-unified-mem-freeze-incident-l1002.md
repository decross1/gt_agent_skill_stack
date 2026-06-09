---
slug: "runlog-exp008-armc-unified-mem-freeze-incident-l1002"
type: "run_log_entry"
date: "2026-06-08"
source: "week1.run.jsonl:1002"
---

# a_bgt_rsi: Nara — week1.run L1002

_safe live run; instead a near-machine-hang -- arm C abandoned on this box_

**Did:** INCIDENT: arm C (util 0.46, ~48GiB weights) launch on the GB10 (121GiB UNIFIED mem) thrashed the system -- SSH + UI tracking went down. Root cause: unified memory feeds GPU AND OS; loading a 2nd ~48GiB model alongside the 48GiB production g…

**Observed:** status=recovered day= duration_ms=None fallback=None

## Referenced by

- `correction-exp008-armc-gb10-unified-mem-oom-2026-06-09` (correction) — **derived_from**
