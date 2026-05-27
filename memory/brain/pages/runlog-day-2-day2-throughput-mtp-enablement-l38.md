---
slug: "runlog-day-2-day2-throughput-mtp-enablement-l38"
type: "run_log_entry"
date: "2026-05-19"
source: "week1.run.jsonl:38"
---

# a_bgt_rsi: Nara — week1.run L38

_single-stream decode throughput tuned to clear the 40 tok/s sweep floor_

**Did:** Resolved the day_2 throughput abort. Empirically determined vLLM v0.20.0 ships no Gemma 4 MTP support (no gemma4_mtp.py, no Gemma4MTPModel registry entry); PR #41745 (merged 2026-05-06 @ 27e0057) first appears in v0.21.0. Re-pinned image vl…

**Observed:** status=passed day=day_2 duration_ms=0 fallback=None
