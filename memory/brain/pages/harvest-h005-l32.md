---
slug: "harvest-h005-l32"
type: "harvest_finding"
date: "2026-05-24"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-fallback", dst_type: "skill"}
---

# H005 — fallback:gap

_week1.run.jsonl L116-L123 (slip ladder day7.1/7.2/7.3 → resolved)_

**Source skill:** `fallback`

**Class:** gap

**Ref:** week1.run.jsonl L116-L123 (slip ladder day7.1/7.2/7.3 → resolved)

**Source project:** a_bgt_rsi

**Evidence:** Day 7 used a 'slip ladder' protocol: the PD experiment ran into expected-range overshoot; instead of failing or escalating, the consumer slipped the deadline by one day (slip_declared L117), ran again (partial_pass L118), slipped again (L119), ran again (L120), slipped again (L121), ran the diagnostic variant (L122), then resolved (L123). Each slip was its own logged entry with a stated reason and reset budget. fallback covers 'switch to a known alternative' but not 'extend the deadline, same approach, capped slip count'. The slip-ladder is a general deferred-work protocol — bounded, logged, with a resolution criterion — the framework has no skill for.

**Plan candidate:** new skill or fallback-section: `slip-ladder` — declare a bounded sequence of deadline extensions; each slip is logged with reason + new cap; resolution criterion declared upfront; auto-escalates if cap exceeded.

## Links

- **about** → `skill-fallback` (skill)
