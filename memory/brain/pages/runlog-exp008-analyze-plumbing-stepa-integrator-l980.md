---
slug: "runlog-exp008-analyze-plumbing-stepa-integrator-l980"
type: "run_log_entry"
date: "2026-06-08"
source: "week1.run.jsonl:980"
---

# a_bgt_rsi: Nara — week1.run L980

_exp008 analyze.py consumes eval-driver output and emits H0/H1/INSUFFICIENT with all 3 decision metrics decision-eligible (n>=10), and a turn-key read-only pin reference path exists_

**Did:** Step-A integrator prep so a live exp008 run yields a verdict not INSUFFICIENT: (1) eval_novelty + eval_toolcall now emit analyze-shaped {arm,metric,value} rows to metrics_<eval>_<arm>.jsonl (novelty_agreement+calibration_error per-fixture; …

**Observed:** status=passed day= duration_ms=None fallback=None
