---
slug: "proposal-p-004"
type: "proposal"
date: "2026-05-25"
source: "memory/brain/proposals.jsonl"
edges:
  - {type: targets, dst: "skill-spawn-contract", dst_type: "skill"}
---

# P-004 — Add `state_basis` field to spawn-contract contract block

_agent: claude-code-main_

**Verdict:** `accepted`

**Target:** skill → `spawn-contract`

**Change:** Extend the contract schema with `state_basis: 'parent_working_tree' | 'parent_head' | 'inlined_only'` (default 'inlined_only'). Specifies which view of the world the child operates against. Worktree-isolated spawns naturally land at 'parent_head' (or earlier); a child that must reflect the parent's current uncommitted state needs 'parent_working_tree' (which then forbids worktree isolation OR requires the parent to commit/stash before launch). Surfaces the divergence S22 SP-002 discovered.

**Reasoning:** SP-002 (the first real spawn-contract execution) surfaced that worktree isolation hides parent's uncommitted state from the child — silent divergence between criterion intent and child's view. Adding `state_basis` makes this an explicit contract concern that the writer thinks about, so the choice between auth-enforcement (worktree) and state-currency (parent tree) is deliberate. Rule-aligned: no rule currently covers this. Audit-found, not theoretical.

**References:** `SP-002`, `spawn-contract`

**Verdict reasoning:** Implemented this session: .agents/skills/spawn-contract/SKILL.md grew a `state_basis` field in the contract block (HEAD@<sha> | working-tree@<parent-sha> | snapshot:<path> | in-prompt) and a Rule that the state_basis is explicit. Worked example references SP-002 (the 18-vs-24-skills finding). Also: spawn entries are now projected as first-class brain nodes with edges to the skills they declare in skill_subset — the brain can answer 'which agent spawned what under which contract.'

## Links

- **targets** → `skill-spawn-contract` (skill)
