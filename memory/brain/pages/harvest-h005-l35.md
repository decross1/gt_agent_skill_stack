---
slug: "harvest-h005-l35"
type: "harvest_finding"
date: "2026-05-24"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-decision-log", dst_type: "skill"}
---

# H005 — decision-log:confirmed

_DECISIONS.md D-028 Day-7 publication disposition_

**Source skill:** `decision-log`

**Class:** confirmed

**Ref:** DECISIONS.md D-028 Day-7 publication disposition

**Source project:** a_bgt_rsi

**Evidence:** D-028 records a Day-7 finding (cooperation lock-in observed for Gemma 4) and the disposition (not published standalone because it's a model prior, not a result). Entry uses the decision-log format with explicit alternatives (publish anyway / not publish) and rationale (prior, not result). Confirms S8's decision-log skill is being used as designed — including for *negative* dispositions, which are exactly the kind that go unrecorded without the skill.

## Links

- **about** → `skill-decision-log` (skill)
