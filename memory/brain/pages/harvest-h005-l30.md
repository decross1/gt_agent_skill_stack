---
slug: "harvest-h005-l30"
type: "harvest_finding"
date: "2026-05-24"
source: "memory/feedback.jsonl"
---

# H005 — run-log:friction

_week1.run.jsonl L114,L117,L119,L121,L123,L125_

**Source skill:** `run-log`

**Class:** friction

**Ref:** week1.run.jsonl L114,L117,L119,L121,L123,L125

**Source project:** a_bgt_rsi

**Evidence:** 4 new status values used by the consumer that run-log's default enum (started/passed/partial_pass/failed/aborted/halted/escalated/skipped) does not name: 'correction' (L114, semantic re-record of a prior task), 'slip_declared' (L117/L119/L121, time-cap slipped), 'slip_resolved' (L123, slip closed), 'gate_armed' (L125, gate pre-armed not yet halted). The S10 'non-exhaustive default a project may extend' clause covers them in principle, but four organic extensions in one week across three harvests (H003 had 'escalated', H001 had 'started') suggests the default is systematically incomplete — slipping and gate-arming in particular look general, not consumer-specific.

**Plan candidate:** run-log: consider adding `slip_declared`/`slip_resolved` and `gate_armed` to the default enum, or document an explicit 'when to extend' guidance.
