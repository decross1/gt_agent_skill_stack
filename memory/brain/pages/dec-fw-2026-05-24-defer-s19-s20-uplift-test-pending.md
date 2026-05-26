---
slug: "dec-fw-2026-05-24-defer-s19-s20-uplift-test-pending"
type: "decision"
date: "2026-05-24"
source: "memory/DECISIONS.md"
---

# 2026-05-24 — Defer S19-S20 uplift test pending consumer choice

_framework decision_

**Decision:** Defer the Phase-4 uplift test (S19-S20: onboard a second,
less-disciplined consumer, run it with and without the runtime-safe core,
measure audit-completeness uplift). No consumer is being chosen at this
time; the gate `s19_choose_uplift_consumer` clears as
*deferred-by-human-choice*. Advance to S21 (Phase 5).
**Alternatives considered:**
(a) Spin up a toy `latency-probe` project — rejected for now: no immediate
    appetite, and a toy's realism is bounded.
(b) Spin up a toy RAG eval harness — rejected for now: same reasoning.
(c) Adopt an existing real project — rejected for now: no named candidate;
    higher scope risk than a toy without proportional payoff today.
(d) Proceed to Phase 5 (S21+) — **chosen.**
**Rationale:** The Charter's uplift claim is structurally testable only
with a less-disciplined second consumer; doing it well requires
deliberate setup that the user is not ready to commit to today. Phase 5
(autonomous spawned agents) does not depend on uplift evidence being
gathered first. The deferral is recorded so v1.0 (S24) can be honest
that uplift remains untested — or so a future session can pick it up.
**Reversibility:** trivial — return to S19 when a consumer is named;
all S19-S20 plan content remains in `plan.md`.
**Supersedes:** none.
