---
slug: "harvest-h002-l25"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-decision-log", dst_type: "skill"}
---

# H002 — decision-log:gap

_a_bgt_rsi DECISIONS.md D-001..D-025_

**Source skill:** `decision-log`

**Class:** gap

**Ref:** a_bgt_rsi DECISIONS.md D-001..D-025

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi keeps a 25-entry decision log where every entry carries Date / Decision / Alternatives considered / Rationale / Reversibility / Supersedes, with explicit supersedes-chains (D-022>D-020>D-003) and dated in-place updates (D-019). The framework treats DECISIONS.md as a passive memory file with a thin decision/why/supersedes format and has no skill governing how to write a decision entry.

**Plan candidate:** new skill 'decision-log': capture Alternatives + Reversibility as mandatory fields and maintain supersedes-chains — adopt a_bgt_rsi's D-xxx format.

## Links

- **about** → `skill-decision-log` (skill)
