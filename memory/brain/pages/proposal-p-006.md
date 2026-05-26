---
slug: "proposal-p-006"
type: "proposal"
date: "2026-05-25"
source: "memory/brain/proposals.jsonl"
---

# P-006 — Feedback-loop visibility: harvest findings as first-class graph nodes

_agent: claude-code-main_

**Verdict:** `accepted`

**Target:** page → `feedback.jsonl`

**Change:** Promote memory/feedback.jsonl entries to brain graph nodes of type `harvest_finding`. Each finding gets a page (id = harvest_id + skill, e.g. H005-run-log-friction) with edges: `references` → the source run-log task_id; `bears_on` → the target skill (e.g. run-log SKILL.md). Surfaces the feedback loop (consumer activity → harvest finding → skill change) as a walkable subgraph instead of a hidden JSONL.

**Reasoning:** User feedback 2026-05-25: 'I do want to see the other information like the skills that are being proposed by the agents, the feedback loop for improving, etc.' Today only proposals are in the graph; harvest findings (the upstream of proposals) are invisible. Closing this loop is what makes the graph genuinely useful for understanding framework evolution.

**References:** `feedback.jsonl`, `project_pages.py`, `harvest`

**Verdict reasoning:** Implemented during the N2+P-006 session 2026-05-26. scripts/project_pages.py gained synthesize_loop_entities() which projects harvest_finding (from feedback.jsonl), proposal (from proposals.jsonl), and rule (from rules.md) as first-class graph nodes, plus the loop edges: harvest_finding -becomes-> proposal, correction -enacts-> rule, proposal -auto_rejected_by-> rule, and proposal -produces-> decision (hooked for future use when decision_id is populated). graph.html gained a 'Loop' filter group (default-on) and three distinct TYPE_COLORS (indigo/amber/emerald). Verified: 42 harvest_finding + 7 proposal + 2 rule nodes projected; 4 loop edges visible (H006->P-003 becomes; corrections->FR-001/FR-002 enacts; P-002->FR-001 auto_rejected_by). proposal_health.py (the N2 deliverable) is intentionally NOT wired into the graph sidebar per session-design choice (independent tools). Backlog finding: P-003.references cites feedback.jsonl:H006 but reasoning text refers to H005 — data-entry typo worth surfacing as a future cleanup.
