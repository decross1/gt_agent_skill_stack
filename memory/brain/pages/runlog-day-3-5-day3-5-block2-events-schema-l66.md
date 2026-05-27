---
slug: "runlog-day-3-5-day3-5-block2-events-schema-l66"
type: "run_log_entry"
date: "2026-05-20"
source: "week1.run.jsonl:66"
---

# a_bgt_rsi: Nara — week1.run L66

_schema is valid Draft 2020-12; happy-path of each branch validates; event_type discriminator routes correctly_

**Did:** Track B delivered schema/events.jsonl.schema.json with root oneOf over two const-discriminated branches (event_type human_intervention | calibration_entry), both additionalProperties:false. human_intervention: timestamp/task_id/subtype(enum…

**Observed:** status=passed day=day_3_5 duration_ms=0 fallback=None
