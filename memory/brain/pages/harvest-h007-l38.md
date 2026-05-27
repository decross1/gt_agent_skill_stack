---
slug: "harvest-h007-l38"
type: "harvest_finding"
date: "2026-05-25"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-run-log", dst_type: "skill"}
---

# H007 — run-log:friction

_week1.run.jsonl L138,L149,L150,L154_

**Source skill:** `run-log`

**Class:** friction

**Ref:** week1.run.jsonl L138,L149,L150,L154

**Source project:** a_bgt_rsi

**Evidence:** Day 8 added FOUR more status values not in run-log's default enum (started/passed/partial_pass/failed/aborted/halted/escalated/skipped): 'open' (L138 day_start, an opening sentinel like 'started' but day-level), 'recorded' (L149 retrospective_recorded, attestation-style completion), 'applied' (L150 tier_shift, mutation-style completion), 'closed' (L154 day_end, closing sentinel). With H005's correction/slip_declared/slip_resolved/gate_armed, the consumer has now invented EIGHT status values across the project that the framework's default enum lacks. This is no longer 'project extension' — the default is systematically incomplete for plan-driven work with day-bounded units, attestation completions, and pre-emptive gates. Either the default enum should grow, or the rule should be 'use these standard categories' with project values flagged as a different field.

**Plan candidate:** run-log: split the field into status (closed enum: started/passed/partial_pass/failed/aborted/halted/escalated/skipped) + status_qualifier (free-form project word like slip_declared/tier_shift). OR expand the default to include day_start/day_end/attestation_recorded/mutation_applied. Pick before v1.0.

## Links

- **about** → `skill-run-log` (skill)
