---
slug: "harvest-h002-l15"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-investigate", dst_type: "skill"}
---

# H002 — investigate:confirmed

_DECISIONS.md D-021; week1.run.jsonl L37_

**Source skill:** `investigate`

**Class:** confirmed

**Ref:** DECISIONS.md D-021; week1.run.jsonl L37

**Source project:** a_bgt_rsi

**Evidence:** D-021's E1 experiment locked the GPU clock (one variable), saw 0% throughput change, and eliminated the compute-bound hypothesis. L37 fit latency=f(output_tokens) to refute the 'measurement artifact' hypothesis and reach a root cause. Matches investigate's hypothesis-tree, one-variable-per-test, root-cause-not-symptom.

## Links

- **about** → `skill-investigate` (skill)
