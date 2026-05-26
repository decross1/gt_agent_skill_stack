---
slug: "s22-5-narrate-sp-002-lifecycle"
type: "reflection"
date: "2026-05-25"
source: "memory/brain/narratives.jsonl"
---

# s22_5_narrate_sp_002_lifecycle

**Intent:** Run the spawn-contract protocol against a real Agent-tool child (not a structural mock). Establish that the lifecycle (contract before launch → real spawn → child reports → parent reconciles via validate) holds end-to-end and surface anything the mock could not.

**Did:** Wrote SP-002 contract to spawn.jsonl (skill-frontmatter audit; read-only auth cap; 300s budget; reporting via final agent text). Launched an auditor child with isolation=worktree as belt-and-suspenders on the auth cap. Child returned a well-formed JSON summary in 24 seconds. Parsed, validated against done_condition (8 sub-checks), appended completed entry with result block.

**Observed:** Done-condition validates PASS as written. But: the child reported total=18 while the parent's working tree has total=24. The worktree was branched from HEAD (which lags behind the parent's working tree by 6 uncommitted new skills + 14 modified files); the child therefore audited HEAD's state, not the parent's current view. The result is internally consistent and the child obeyed the contract perfectly — but the criterion's *intent* (current state) was silently mis-targeted by the choice to use worktree isolation. Two findings worth keeping: (1) worktree isolation is a strong authority enforcer but also an unintended state isolator; (2) the spawn-contract pattern surfaced this divergence cleanly via the structured result + parent_observations — it would have been invisible in plain orchestrate.

**Would do differently:** For audits that must reflect parent's current working tree: either skip worktree isolation (rely on declarative auth cap + child's honor) OR commit pending state before the spawn OR inline the data in the prompt rather than have the child re-read from disk. For pure-function tasks (analyze this fixed input), worktree isolation is the right call. The contract's task_statement should specify which world the child is operating in — 'current parent working tree' vs 'HEAD-of-branch' vs 'whatever you receive in this prompt'. Propose adding a `state_basis` field to the contract schema for v1.0 — pending in proposal queue.

**Corrections honored:** FR-001 (suspicious-clean 100% metrics), FR-002 (run-log canonical over state during gate-armed holds)
