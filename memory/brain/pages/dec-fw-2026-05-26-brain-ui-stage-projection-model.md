---
slug: "dec-fw-2026-05-26-brain-ui-stage-projection-model"
type: "decision"
date: "2026-05-26"
source: "memory/DECISIONS.md"
---

# 2026-05-26 — Brain UI: stage projection model (collapse dispatch+receipt+call per worker)

_framework decision_

**Decision:** In `scripts/project_pages.py::synthesize_stages`, collapse each
`(iteration, tool)` triple — `loop_v0_tool_dispatch` event + `loop_v0_tool_receipt`
event + the vLLM call they wrap — into one synthetic **`stage`** node per worker.
Stage entities live only in `graph_data.js` / `pages/`; the underlying narratives
and edges in `narratives.jsonl` / `edges.jsonl` are untouched. Stages get a
per-worker color (Hypothesize/Retrieve/Novelty/Critique/Journal) so the per-
iteration pipeline reads at a glance.
**Alternatives considered:**
(a) Hide mechanical nodes entirely via filter — rejected: lineage debugging
    becomes impossible.
(b) Emit stages into `edges.jsonl` + a new narrative type — rejected: pollutes
    the canonical append-only ledger with derived data; re-projection would
    require schema versioning.
(c) Defer to per-iteration markdown rendering (no graph nodes) — rejected:
    loses the cross-iteration comparability that the graph affords.
**Rationale:** The user's "I can't tell what is doing what" feedback was about
the graph being 78% mechanical noise. Stages are a *view* over the raw data —
turning them on/off is a UI concern, not a data concern. Keeping the synthesis
in `project_pages.py` keeps `edges.jsonl` clean (only narrate / ingest emit
there) and means we can change the stage model without migrating data.
**Reversibility:** trivial — delete `synthesize_stages()` and the edge filter
in `project_pages.py::main()`. Brain reverts to the iter+event+call view.
**Supersedes:** none.
