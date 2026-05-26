---
slug: "proposal-p-003"
type: "proposal"
date: "2026-05-24"
source: "memory/brain/proposals.jsonl"
---

# P-003 — New Layer-B skill: `slip-ladder` for bounded deadline extensions

_agent: claude-code-main_

**Verdict:** `accepted`

**Target:** skill → `slip-ladder`

**Change:** Author .agents/skills/slip-ladder/SKILL.md (Layer B, runtime-safe false). Defines: declare a bounded sequence of deadline extensions; each slip is logged with reason + new cap; resolution criterion declared upfront; auto-escalates if cap exceeded. Companion to [[fallback]] (fallback covers 'switch to an alternative'; slip-ladder covers 'extend the deadline, same approach').

**Reasoning:** H005 finding (fallback/gap): the consumer's Day-7 slip ladder (7.1/7.2/7.3 → resolved) is a general deferred-work protocol the framework has no skill for. Filing as a proposal rather than authoring directly because the skill name, scope, and overlap with [[fallback]] need human judgment.

**References:** `feedback.jsonl:H006`, `fallback`

**Verdict reasoning:** Approved by the user 2026-05-24 with the wording 'accept slip-ladder as a new skill'. Authored as .agents/skills/slip-ladder/SKILL.md (Layer B, runtime-safe false — matches the original proposal). Constructed to satisfy the runtime-safe contract (no human required, no PR/harness call, append-only logging, closed dependency set) so a future Layer-A promotion is a frontmatter flip if a runtime use-case emerges. Six-rung skeleton: declare cap + per-slip budget + resolution criterion + diagnostic-variant tag upfront; each slip is its own logged event; cap-exceeded → escalated, never more slips.

## Referenced by

- `harvest-h006-l36` (harvest_finding) — **becomes**
