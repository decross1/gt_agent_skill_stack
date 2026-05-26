---
slug: "dec-fw-2026-05-26-brain-ui-decisions-removed-from"
type: "decision"
date: "2026-05-26"
source: "memory/DECISIONS.md"
---

# 2026-05-26 — Brain UI: decisions removed from graph by default; dedicated tab

_framework decision_

**Decision:** `decision` type moves out of the **Research** filter group into a
new **History** group with `defaultOn: false`. The graph default-hides all 40
decision nodes. The sidebar gains a **Decisions** tab listing them newest-first
with framework/apparatus side badge, clicking a row renders the full decision
page in the panel. Decision nodes remain in `DATA.nodes` so cross-reference
edges (correction `references` decision) still resolve when followed from
another node's sidebar.
**Alternatives considered:**
(a) Drop decisions from `graph_data.js` entirely — rejected: breaks
    correction→decision navigation.
(b) Keep decisions in Research filter group, default on — rejected: 40 decision
    nodes dominate a graph designed for iteration walking.
(c) Show decisions only when a correction is selected — rejected: too clever,
    surprising UX.
**Rationale:** Decisions are durable history, not active research. A flat
chronological list is the right interaction (`What did we decide on date X?`)
— the graph adds nothing. Keeping them in `DATA.nodes` preserves brain
integrity (every page is graphable on demand) without committing to drawing
them all every render.
**Reversibility:** trivial — move `decision` back into `FILTER_GROUPS.research`
in `graph.html`. The tab survives the change as a bonus access path.
**Supersedes:** none.
