---
slug: "dec-fw-2026-06-10-two-surface-observability-design-system-ui"
type: "decision"
date: "2026-06-10"
source: "memory/DECISIONS.md"
---

# 2026-06-10 — Two-surface observability design system (UI overhaul)

_framework decision_

**Decision.** (1) Two surfaces, one design language: apparatus :5173 = runtime
ops + escalation inbox hero; brain :5174 = governance (file-first static).
Shared token block byte-mirrored in both repos, enforced by
`scripts/check_design_tokens.py` (framework reads consumer — firewall-correct
direction). (2) The brain graph is re-scoped from whole-brain event hairball to
an **agent↔skill cluster map**: packs as hulls, usage-weighted edges
(solid=explicit `skill_used`, dashed=inferred via the attribution ladder),
governance painted on nodes (drift halo / healed pulse / fresh outline /
by-design muted / runtime-safe ring); event lineage is a scoped ego-mode
(≤2 hops), not a destination. (3) Escalation is severity×reversibility-tiered
(state_gate > stale_run > gate/finding review > bubble-info) with one-decision
cards; copy-paste CLI demoted to fallback once D-046 in-UI attestation is live.

**Alternatives.** Unify both UIs into the React app (rejected: breaks brain
file-first doctrine, burns budget on migration); keep the force-directed
whole-brain graph as a co-equal view (rejected by user: wrong medium for
overview — structure views carry overview, graphs carry relationships);
replace node-link entirely with matrix/timeline (rejected: loses the
agent↔skill relationship medium the user explicitly wanted).

**Rationale.** Research synthesis (overview-first/details-on-demand, 5–9
element ceiling, RAG reserved for state, color-as-identity per agent,
graph-for-structure vs timeline-for-time) + judged mockup competition
(m1 stack won 24/25 on identical data; SPEC.md is the build contract).

**Reversibility.** Medium — static pages + generators are replaceable;
schema v2 of summary.json is the load-bearing contract (consumers: both
dashboard pages, verify_brain_view).
