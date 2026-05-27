---
slug: "runlog-day-1-day1-block2-unbox-l11"
type: "run_log_entry"
date: "2026-05-18"
source: "week1.run.jsonl:11"
---

# a_bgt_rsi: Nara — week1.run L11

_power LED solid; fan low RPM; DGX dashboard reachable (curl 2xx OR ping succeeds)_

**Did:** ping 10.0.0.73 3/3 received 0% loss (reachability check passes on ping per pass_signal); curl http://10.0.0.73/ refused on :80 — no HTTP service on port 80, non-fatal; LED/fan per human attestation

**Observed:** status=passed day=day_1 duration_ms=0 fallback=None
