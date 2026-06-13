---
slug: "proposal-p-018"
type: "proposal"
date: "2026-06-10"
source: "memory/brain/proposals.jsonl"
edges:
  - {type: targets, dst: "skill-spawn-contract", dst_type: "skill"}
---

# P-018 — spawn-contract/workflow: verify the limb's fork base against state_basis before building

_agent: claude-code-main_

**Verdict:** `open`

**Target:** skill → `spawn-contract`

**Change:** Add to the spawn-contract skill (and the workflow-limb prompt template it generates): the FIRST act of a worktree-isolated limb is to check git rev-parse HEAD against the contract's state_basis; on mismatch, hard-reset to the contracted base (clean tree) or escalate - never build on the discovered base. Today this is folk practice; make it a contract clause.

**Reasoning:** 2026-06-10 build workflow wf_d4e96978-59a: ALL FOUR limb worktrees were created at stale base 30e85c3 (an exp008-era commit; the harness's worktree pool reused old branches) instead of the contracted 8ece354. Every limb independently caught it ONLY because the contract carried state_basis and the prompt restated the HEAD - one limb building on 30e85c3 would have produced patches against files that did not exist yet (the design docs name this as 'the exact CLAUDE.md discipline-3 failure mode'). Four independent self-corrections is luck wearing a seatbelt; a contract clause makes it deterministic.

## Links

- **targets** → `skill-spawn-contract` (skill)
