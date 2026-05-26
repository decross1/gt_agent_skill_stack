---
slug: "dec-ap-d-032-install-full-agent-system-skill-set"
type: "decision"
date: "2026-05-26"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-032 — Install full `agent_system` skill set into `.agents/` (diverges from BOUNDARY.md)

_apparatus decision_

**Date locked.** 2026-05-26 (LOOP_V0 Part 1, primary session).

**Decision.** Install all 24 skills + 4 agent profiles from
`agent_system` into `a_bgt_rsi/.agents/` as symlinks, with no
runtime-safe filter. This includes the dev-only skills
(`code-review`, `experiment`, `health`, `investigate`,
`plan-research`, `repro-check`, `ship`, `context-save`,
`context-restore`, `orchestrate`, `harvest`, `narrate`,
`decision-log`, `propose`, `review-proposal`, `slip-ladder`,
`auto-experiment`, `spawn-contract`, `brain-recall`) that
`agent_system/BOUNDARY.md` recommends NOT installing into a
project's runtime.

**Alternatives.**

1. Install only the 5 runtime-safe core skills (`resume-state`,
   `gate-check`, `validate`, `run-log`, `fallback`). Honors
   BOUNDARY.md strictly. Considered and rejected.
2. Install all skills but mark them dev-time-only in this project
   (Nara sees only runtime-safe at runtime). Adds a new layer.
3. The chosen path: install everything, document the divergence.

**Rationale.**

The user explicitly chose "full skill set, symlinked" with awareness
that this diverges from BOUNDARY.md. Three reasons it makes sense
for *this* project:

1. **Nara is a research orchestrator, not a customer-facing
   runtime.** BOUNDARY.md's rule is shaped for production agent
   systems where dev-only skills (code-review, ship) would be
   inappropriate when an agent acts on behalf of a user. Nara
   acts on behalf of one researcher (the framework's author),
   and the dev/runtime line is less sharp here than in a
   product context.

2. **Some "dev-only" skills are valuable for research workflows.**
   `experiment`, `repro-check`, `auto-experiment`, `decision-log`
   speak directly to what Nara needs to do well. The
   `runtime-safe` label was set in 2026-05; a fresh look might
   reclassify some of them.

3. **Reversibility is trivial.** If a dev-only skill turns out to
   create problems (e.g., Nara invoking `ship` autonomously), the
   per-skill symlink can be removed from `.agents/skills/` without
   touching the framework.

**What `agent_system/BOUNDARY.md` actually says.** Two skill
classes, by frontmatter:

- **Runtime-safe core (Layer A, `runtime-safe: true`)** — five
  execution-discipline skills. Designed to be embedded in a
  runtime agent.
- **Dev-only (Layers B/C, `runtime-safe: false`)** — research
  vertical + orchestration/meta. "Must never be loaded into any
  project's runtime agent."

This project consciously diverges from the second rule.

**Reversibility.** Per-skill: `rm a_bgt_rsi/.agents/skills/<skill_name>`.
Wholesale revert to runtime-safe only:
`agent_system/install.sh --uninstall && agent_system/install.sh --target-path a_bgt_rsi/.agents/skills --filter runtime-safe`.

**What would reverse the divergence.** (1) A dev-only skill causes
Nara to take an action the human did not want (e.g., autonomously
shipping code, opening PRs). (2) Re-thinking the dev/runtime line
in `agent_system/BOUNDARY.md` and reclassifying some skills as
runtime-safe. (3) The project crosses a maturity threshold where
"this is a research workflow tool, not a product runtime" no longer
holds — at which point honoring BOUNDARY.md becomes important.

**Documented at:** `.agents/README.md` and `agent/README.md`.

---
