---
slug: "harvest-h002-l8"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
---

# H002 — gate-check:confirmed

_week1.run.jsonl L19,L35 task=state_transition_

**Source skill:** `gate-check`

**Class:** confirmed

**Ref:** week1.run.jsonl L19,L35 task=state_transition

**Source project:** a_bgt_rsi

**Evidence:** A hard-checkpoint task failing (day1 vLLM serve L19; day2 50-call sweep L35) aborts the whole day rather than being worked around ('per CLAUDE.md rule 6 and on_failure:abort_day, Block 2 halts'). Matches gate-check's hard-checkpoint rule.
