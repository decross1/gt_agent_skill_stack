---
slug: "harvest-h002-l16"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-investigate", dst_type: "skill"}
---

# H002 — investigate:confirmed

_week1.run.jsonl L37,L52_

**Source skill:** `investigate`

**Class:** confirmed

**Ref:** week1.run.jsonl L37,L52

**Source project:** a_bgt_rsi

**Evidence:** Both a suspiciously-low throughput (29.75 tok/s, L37) and a suspiciously-low needle score (0.7221, L52) were given full investigations to determine 'genuine vs artifact' before being accepted. Matches investigate's 'a suspiciously bad result gets the same scrutiny as a failure'.

## Links

- **about** → `skill-investigate` (skill)
