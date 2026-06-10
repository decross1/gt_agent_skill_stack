---
slug: "demo2b-nemoclaw-agent-autonomy"
type: "reflection"
date: "2026-06-09"
source: "memory/brain/narratives.jsonl"
---

# demo2b_nemoclaw_agent_autonomy

**Intent:** Prove full in-sandbox LLM-agent autonomy: Nara (local Gemma in nara-sandbox) forming + running a research thesis via the host tools itself.

**Did:** Authored + installed the nara-research-cycle SKILL.md (path b: instruct the agent to curl the host tool plane), then drove openclaw agent --agent main on local Gemma.

**Observed:** The OpenClaw 'main' agent has only tool_search_code natively (NO shell/exec tool), so it could not execute the SKILL.md curl; it tried an 'exec' tool 14x, found it unavailable, and HONESTLY said so rather than confabulating a snapshot (good agent behavior). Full autonomy requires the host tools as NATIVE MCP tools (path a: an openclaw.json MCP-server block at host.openshell.internal:8077; v2026.5.18 schema unknown -- must not guess into a live config). Took the rule-7 fallback (~20min cap): DEMO 2a (real sandbox-originated run_loop_iteration -> full host iter-2026-06-09-003) stands as the proven write-capable seam; autonomy is the named carryover.

**Would do differently:** Probe the agent's NATIVE tool inventory BEFORE authoring a path-b SKILL.md -- the shell-tool assumption was the load-bearing unknown, and path-a (MCP) was always the real route. Next session: confirm the openclaw.json MCP-server schema from the v2026.5.18 clone/docs, register the tool plane, re-drive.

**Corrections honored:** inviolate-rule-7-fallback, D-013, D-014

## Referenced by

- `agent-integrator` (agent) — **authored**
