---
slug: "proposal-p-005"
type: "proposal"
date: "2026-05-25"
source: "memory/brain/proposals.jsonl"
---

# P-005 — Agent-centric view: group/color graph by agent_id

_agent: claude-code-main_

**Verdict:** `accepted`

**Target:** skill → `graph.html`

**Change:** Add a 'group by agent' mode to graph.html. Each unique agent_id (orchestrator:dispatch, vllm_worker, exp001_tft_player, claude-code-main, builder-subagent, etc.) becomes a coloring dimension and an optional filter. Sidebar tab 'Agents' lists every agent_id with its last-seen timestamp + count of nodes it produced + count of edges it authored. Click an agent → graph isolates to that agent's contributions. Directly answers user's stated goal 'what is each agent doing, and what work is it connected to.'

**Reasoning:** User feedback 2026-05-25: the graph is hard to read partly because no agent-centric framing exists today. The data is there (agent_id in every narrative + apparatus_event) but never surfaced. This is a graph-shape problem that stays inside the graph — does not require pivoting away from the current data model.

**References:** `graph.html`, `narratives.jsonl`, `SP-002`

**Verdict reasoning:** Implemented 2026-05-26: scripts/project_pages.py::kind_from_narrative derives a sub-kind (iteration | orchestrator_event | llm_call) from each narrative's _source.file + agent_id, and memory/brain/view/graph.html gains TYPE_COLORS entries (sky / teal / pink) so the LOOP_V0 lineage renders as three visually distinct layers. Sidebar Title now reads 'a_bgt_rsi: Nara/Orchestrator — week1.run L<N>' (and analogues for Nara / Nara/LLM). Existing apparatus_event narratives reclassify automatically on each project_pages.py run — no re-ingest needed. Approach diverges slightly from the original proposal (kind-driven, not pure agent_id-driven) because kinds map more cleanly to the three-tier graph the user actually walks; agent_id surfaces in the Title instead. Closes the user's 'I can't tell what is doing what' feedback.
