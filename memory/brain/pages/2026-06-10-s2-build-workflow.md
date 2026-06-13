---
slug: "2026-06-10-s2-build-workflow"
type: "reflection"
date: "2026-06-10"
source: "memory/brain/narratives.jsonl"
edges:
  - {type: produced, dst: "D-050", dst_type: "decision"}
  - {type: produced, dst: "D-051", dst_type: "decision"}
---

# 2026-06-10-s2-build-workflow

**Intent:** Execute the human's 2-3h autonomous directive via dynamic workflow: implement the two recorded next-batch fronts (MCP submit+poll at the beta tool plane; D-045 residuals 1+2 via skeptic seams) while a concurrent session executed the UI handoff and a third (S3) built coordinator autonomy in the same checkout.

**Did:** Two-stage workflow: recon (2 read-only design limbs, resumed across an account token-limit stall) -> integrator adjudication -> build (4 worktree-isolated limbs creating only disjoint NEW files, existing-file wiring delivered as tested draft patches) -> serial integration by the primary (9 patches, conftest+schema parity edits) -> two-adversarial-reviewer gate (0 blocking; 7 fixes applied) -> scoped commit cb88c2c, both features env-gated dark. Real smokes explicitly deferred (logged fallback): GPU held by S3's soak; the :8077 restart needed to serve the new tools is human-coordinated (auto-mode correctly denied my pkill).

**Observed:** (1) All 4 build limbs independently caught their worktrees forked from stale base 30e85c3 instead of contracted 8ece354 and self-corrected because the spawn contract carried state_basis - the contract field did real work. (2) Three sessions in one checkout co-existed safely ONLY via file-disjointness checks before every fan-out, worktree isolation for half-built work, append-only shared ledgers, and scoped git-add commits; the morning session swept my in-progress note into its commit, S3 deliberately excluded my files - convention emerged mid-day. (3) The suite count moved 1071->1162 while THREE sessions added tests concurrently with zero collisions - the disjoint-new-test-files norm scales. (4) An account-wide token limit stalls all sessions at once; resumability (workflow resumeFromRunId + ledgers + state files) is what made the 9h gap recoverable.

**Would do differently:** Pin the worktree fork base IN the Workflow call (or verify each limb's HEAD in the script before building) rather than relying on limbs to self-correct; check for concurrent-session dirt BEFORE writing shared files (DECISIONS.md edit collided once and needed a re-read); stage decision entries as the last pre-commit step so they cannot ride into another session's commit.

**Corrections honored:** D-037, D-040, D-043, D-044, D-045, D-047, D-048

## Links

- **produced** → `D-050` (decision)
- **produced** → `D-051` (decision)

## Referenced by

- `agent-claude-code-main` (agent) — **authored**
