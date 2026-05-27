---
slug: "harvest-h002-l24"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-orchestrate", dst_type: "skill"}
---

# H002 — orchestrate:confirmed

_week1.run.jsonl L49,L54-L56_

**Source skill:** `orchestrate`

**Class:** confirmed

**Ref:** week1.run.jsonl L49,L54-L56

**Source project:** a_bgt_rsi

**Evidence:** Work is delegated to builder sub-agents ('authored by a builder sub-agent under Track A authority', L49) and independently checked by auditor sub-agents ('audited by an auditor sub-agent', L54-56) — the verifier is not the author. Matches orchestrate's role decomposition and 'independent verification stays independent'.

## Links

- **about** → `skill-orchestrate` (skill)
