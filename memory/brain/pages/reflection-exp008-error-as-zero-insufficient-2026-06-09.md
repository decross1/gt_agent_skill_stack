---
slug: "reflection-exp008-error-as-zero-insufficient-2026-06-09"
type: "reflection"
date: "2026-06-09"
source: "memory/brain/narratives.jsonl"
edges:
  - {type: derived_from, dst: "runlog-exp008-first-live-run-triage-l1001", dst_type: "run_log_entry"}
---

# Reflection — an errored eval-worker call is not a measurement; scoring it 0 fabricates a verdict (rule 4). Emit decision rows only for genuinely served calls -> down arm reads honest INSUFFICIENT

_apparatus lesson (a_bgt_rsi exp008 error-as-zero)_

**Intent:** Make the exp008 eval drivers honest under infra failure: when an arm endpoint is down, the eval must not let an APIConnectionError masquerade as a quality signal.

**Did:** Reviewed the first live arm-C run: the :8002 container OOM'd, so all 10 qat novelty calls errored, eval_novelty silently scored them predicted=unclear -> agreement 0.0 and emitted 0-valued metric rows; had toolcall also produced 0s, analyze would have emitted a FALSE H0 ('QAT regressed') from a dead container. Fix landed in consumer commit 3b53380: both eval_novelty + eval_toolcall now emit analyze decision rows ONLY for genuinely served calls (status==passed); an errored call is recorded in the audit row but not scored, and eval_toolcall no longer crashes the whole run on one failed call. +2 tests assert errored calls produce no metric row; suite -> 766.

**Observed:** An arm that errors enough now drops below min_sample (10) -> analyze returns honest INSUFFICIENT ('could not measure this arm') instead of a fabricated regression. On the actual run, pin read novelty agreement 0.8 while qat was correctly INSUFFICIENT. This is consumer inviolate rule 4 (never coerce a failure into a pass/fail value) applied at the metric-emission layer, not just the validation layer.

**Would do differently:** none on the fix. Generalize the pattern: any eval/aggregation that turns a worker error into a numeric 0 is an error-as-zero bug; the worker's served/errored status must gate metric emission everywhere, and a below-min_sample arm must surface as INSUFFICIENT rather than a low score.

**Corrections honored:** consumer inviolate rule 4 (validations never silently coerced / error-as-zero)

## Links

- **derived_from** → `runlog-exp008-first-live-run-triage-l1001` (run_log_entry)

## Referenced by

- `agent-claude-code-main` (agent) — **authored**
