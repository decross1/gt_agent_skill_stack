---
slug: "dec-ap-d-030-retire-track-a-b-c-d-autonomy-tiers"
type: "decision"
date: "2026-05-26"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-030 — Retire track-A/B/C/D + autonomy tiers; adopt single-primary + optional-UI session model; LOOP_V0 is active slice

_apparatus decision_

**Date.** 2026-05-26.

**Decision.** Retire the four-track parallel-execution framework
(`agent/orchestration.md`, `agent/ownership.yaml`,
`agent/collision_protocol.md`, `agent/prompts/track_{a,b,c,d}.md`,
`agent/prompts/dispatched_task.md`), the three-tier autonomy
machinery (`agent/autonomy.md`), the 30/60/90-day phase roadmap
(`PHASE_1_ROADMAP.md`), the live day tracker (`current_day.md`), and
the Week-2 seed plan (`week2_plan_seed.md`). Retire the canonical
`plan.yaml` (4,037 lines) and the per-day / per-track notes in
`notes/`. Move all retired files under `archive/` for reference.

Adopt a **single primary Claude Code session + an optional concurrent
UI session** model. The UI session is worktree-isolated to
`ui/` + `ui_plan.md`. No other concurrent sessions. No dispatched
sub-agents. The new prompts are `agent/prompts/main.md` and
`agent/prompts/ui_session.md`.

The active build plan is **LOOP_V0** ([`LOOP_V0.md`](LOOP_V0.md)) —
the literature-only slice of the eight-step intelligence loop in
[`docs/diagrams/intelligence_loop_v5.svg`](docs/diagrams/intelligence_loop_v5.svg).
LOOP_V0 chains six steps (seed → hypothesize → retrieve → novelty-classify
→ critique → journal), explicitly omitting the sandbox / experiment
tier work, the continuous loop, the meta-review synthesis, and the
automated Step-8 gate. Each component is a worker (~100–150 LOC);
the loop driver is one file (~150 LOC).

Per-session working notes live at `human/sessions/YYYY-MM-DD.md` and
replace `human/daily_plan.md` (archived).

**Alternatives considered.**

1. **Keep the tier/track system, build LOOP_V0 under Track A only.**
   Rejected: the ceremony costs (per-day startup matrix, claim
   protocol, ownership zones, tier-shift mechanics, phase-boundary
   alignment evidence) outweigh their benefit when only one or two
   sessions actually run. ~10,600 words of governance for a
   ~2,300-LOC product that has not yet run the intelligence loop
   end-to-end. The framework was designed for a future scale that
   hasn't arrived.
2. **Delete the retired files outright.** Rejected: history is
   load-bearing — `DECISIONS.md` cross-references many of these
   docs; `archive/` preserves them as read-only reference without
   keeping them as active rules.
3. **Keep `plan.yaml` as the active plan; only retire the track
   framework.** Rejected: `plan.yaml` is 4,037 lines built around the
   day-by-day / tier-by-tier model. Its task-level detail is now
   stale (Week-1 specific) and the schema embeds `track`, `target_zone`,
   `dispatchable`, and `autonomy_tier*` fields that no longer apply.
   A short `LOOP_V0.md` replacing it is cleaner than editing it down.
4. **Build a different slice first** (e.g., the synthetic-tier
   sandbox: one full experiment with robustness battery). Rejected:
   the diagrams call novelty evaluation the hardest step and the
   loop-memory layer is named as the differentiator from other
   auto-science systems; LOOP_V0's literature-only slice exercises
   both with minimal new substrate.

**Rationale.**

The retired framework was designed to scale parallel work across
multiple human-launched sessions and orchestrator-dispatched
sub-agents, with autonomy tiers gating which classes of work could
proceed without explicit human approval. In practice the project has
been driven by 1–2 sessions per day. The framework's costs (reading,
maintaining, complying with ~10,600 words of governance docs) have
exceeded its benefits (collision avoidance, parallel speedup,
trust-by-evidence trajectory), and the cost is paid every session.

The system diagrams under `docs/diagrams/` describe what the
apparatus is supposed to do; eight days of build have produced the
substrate but not the loop. LOOP_V0 is the smallest slice that
closes the cognitive half of the loop end-to-end, on existing
substrate, with no new sandbox tier required.

The UI session running concurrently is the one form of parallelism
that the new model keeps, because the human has explicitly named
visual observability of the running loop as a precondition for
trusting subsequent autonomy expansions.

**Reversibility.** Fully reversible. All retired files are in
`archive/` and can be restored with `git mv` if the single-session
model proves insufficient. The decision to revert would itself be a
durable signal that parallelism is needed; the framework can be
revived without rewriting.

**What would reverse this.** (1) LOOP_V0 cannot be built within
~6 sessions of focused work, indicating the substrate is more
fragmented than expected and explicit collision avoidance is needed.
(2) The UI session repeatedly produces merge conflicts despite the
worktree boundary, indicating either the boundary is wrong or the
two-session model is undertheorized. (3) An overnight / continuous
loop becomes the immediate next slice after LOOP_V0, at which point
the orchestrator-dispatched sub-agent pattern (currently in
`archive/agent_prompts/dispatched_task.md`) returns from archive as
the right pattern.

**Supersedes.** D-005 (graduated autonomy, in spirit — the tier
mechanism is retired but the underlying instinct, "human in the loop
until specific evidence permits less," remains). Does not supersede
the inviolate-rules portion of `CLAUDE.md`, which is preserved
verbatim in the rewrite.

---
