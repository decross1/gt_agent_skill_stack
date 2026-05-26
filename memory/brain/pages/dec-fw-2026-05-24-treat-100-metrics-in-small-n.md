---
slug: "dec-fw-2026-05-24-treat-100-metrics-in-small-n"
type: "correction"
date: "2026-05-24"
source: "memory/DECISIONS.md"
edges:
  - {type: references, dst: "anomaly-tool-call-100pct", dst_type: "anomaly"}
---

# 2026-05-24 — Treat 100% metrics in small-N tests as suspicious-clean

_framework decision_

**Decision:** When a research metric reads exactly 100% (or 0%) on a small-N
test driven by a strongly-directive prompt, do not treat the result as
evidence of robustness. Investigate the prompt and the N before adopting.
**Correction:** Default to disbelieving small-N clean reads; raise N or
soften the prompt before trusting.
**Alternatives:** (a) trust the metric and ship — rejected, this is how
prior-driven results get over-claimed (cf. D-028 cooperation lock-in is a
Gemma 4 prior); (b) widen the test set silently — rejected, hides the
methodological constraint.
**Rationale:** Day-4 tool_call_invocation_rate=1.00 on the e2e set (see
brain page `anomaly-tool-call-100pct`) was driven by a system prompt
mandating tool use. A 100% metric on a small N with a strong directive
prompt is structurally biased upward, not a robustness signal.
**Reversibility:** trivial — single-line rule of practice, no infra
implication.
**Supersedes:** none

## Links

- **references** → `anomaly-tool-call-100pct` (anomaly)

## Referenced by

- `anomaly-tool-call-100pct` (anomaly) — **linked_to**
