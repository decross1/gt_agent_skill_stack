---
slug: "harvest-h003-l27"
type: "harvest_finding"
date: "2026-05-22"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-validate", dst_type: "skill"}
---

# H003 — validate:confirmed

_week1.run.jsonl L85 task=day5_block2_ml_intern_router_

**Source skill:** `validate`

**Class:** confirmed

**Ref:** week1.run.jsonl L85 task=day5_block2_ml_intern_router

**Source project:** a_bgt_rsi

**Evidence:** The ML-Intern probe failed; the actual failure mode (integration-surface mismatch — no requirements.txt, no examples/, a FastAPI app not a library) was reported accurately and explicitly NOT relabeled as the plan's anticipated cause ('ARM64 install failure'). Matches validate's 'mismatches are reported, never recoded'.

## Links

- **about** → `skill-validate` (skill)
