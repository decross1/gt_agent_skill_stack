---
slug: "dec-ap-d-012-dual-model-routing-layer-excluded"
type: "decision"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-012 — Dual-model routing layer excluded

_apparatus decision_

**Date locked.** Technical plan v1, April 30, 2026.
**Decision.** No automatic routing layer that dispatches between Gemma 4
and Qwen 3.6. The architecture supports model swaps via single command;
swaps are manual, when a specific bottleneck is identified.
**Alternatives.**
- Build a routing layer now.
- Build one when a second model is introduced (Week 2–3).
**Rationale.** Premature optimization. A routing layer adds complexity
(routing rules, fallback handling, observability per model) before the
problem it solves has been validated. Start with one model. If
autoresearch coding modifications fail too often, manually swap to Qwen
3.6 for *that workload only*. Don't build infrastructure for a problem
that hasn't been validated yet.
**Reversibility.** Easy. Adding a router later is straightforward; the
worker contract (Day 6) is already designed to accept a `model` field on
the task.

---
