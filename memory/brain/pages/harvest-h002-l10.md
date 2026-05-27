---
slug: "harvest-h002-l10"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-validate", dst_type: "skill"}
---

# H002 — validate:confirmed

_week1.run.jsonl L34,L76_

**Source skill:** `validate`

**Class:** confirmed

**Ref:** week1.run.jsonl L34,L76

**Source project:** a_bgt_rsi

**Evidence:** L34: a 5-check sweep reports each check independently; check #3 (29.75 vs 40 floor) reported FAIL, 'Not coerced — reported as FAIL per CLAUDE.md rule 4'. L76: day4 end-of-day logged partial_pass with a finding field rather than inflating runs. Matches validate's 'each criterion its own check; a near-miss is a fail; never coerce'.

## Links

- **about** → `skill-validate` (skill)
