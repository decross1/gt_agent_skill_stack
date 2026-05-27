---
slug: "harvest-h002-l23"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-orchestrate", dst_type: "skill"}
---

# H002 — orchestrate:gap

_week1.run.jsonl L54-L60,L79-L80_

**Source skill:** `orchestrate`

**Class:** gap

**Ref:** week1.run.jsonl L54-L60,L79-L80

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi runs a 4-track parallel system on git worktrees with discipline orchestrate does not mention: per-track file-boundary allow-lists (L54-56 'File-boundary check PASS'), pre-merge boundary verification ('git diff --name-only main..worktree-X', L79-80), a '--no-ff' merge protocol (L58-60), mock-LLM isolation for side tracks, and completion sentinels ('TRACK C COMPLETE — ready to merge'). orchestrate covers role decomposition but not parallel-worktree execution.

**Plan candidate:** orchestrate (or a new skill): add a parallel-worktree execution protocol — per-track file-boundary allow-lists, mock isolation, pre-merge boundary verification, --no-ff merges, completion sentinels.

## Links

- **about** → `skill-orchestrate` (skill)
