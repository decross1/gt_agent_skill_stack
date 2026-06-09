---
slug: "dec-ap-d-037-authorize-dynamic-workflows-amend-d-030-s"
type: "decision"
date: "2026-06-05"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-037 — Authorize Dynamic Workflows; amend D-030's single-session constraint

_apparatus decision_

**Date locked.** 2026-06-05.

**Amends.** D-030 — the single-primary operating model is amended, not revoked.

**correction:** Local constraints written for previous-generation tooling must not rate-limit newer shipped Claude Code capabilities. When a managed, bounded, observable primitive ships that handles the failure modes an old prohibition guarded against, amend the prohibition rather than letting it cap the new capability.

**Decision.** Dynamic Workflows (the `Workflow` primitive shipped 2026-05-28 with Opus 4.8) are **permitted** and are the **default vehicle** for parallelizable build / audit / research work in the primary session. D-030's "no dispatched coding agents / no multi-worktree matrices" ban is amended: it still governs *manual* parallel human/Claude sessions (the retired track-A/B/C/D machinery); it does **not** govern the Workflow primitive.

**Why D-030 doesn't apply to Workflows.** D-030 reacted to pre-2026-05 tooling — hand-rolled multi-worktree day-matrices with claim-and-lock coordination that produced merge chaos and stale-HEAD forks. Dynamic Workflows removes the conditions that motivated the ban:

- **Bounded.** Runtime caps a run at 16 concurrent / 1000 total agents; no runaway fan-out.
- **Observable.** `/workflows` shows live per-agent progress + token cost.
- **Context-isolated.** The orchestration script (not Claude's context) holds the loop and intermediate state; the parent only sees the synthesized result.
- **Resumable.** Same script + same args replays cached agent results.

**The guardrails that DO stay** (codified in `CLAUDE.md` §"Dynamic Workflow discipline"): inviolate rules inherit to every subagent; **parallel limbs / serial spine** (build agents create disjoint new files; a single serial integrator owns `orchestrator/nara.py` + `orchestrator/tool_registry.py` + `schema/iteration_record.schema.json`); spawn-contract per build agent; single human-authority commit gate after `code-review` + full suite + real smoke; workflow phases log to `run_state/week1.run.jsonl`. These preserve the SDLC discipline D-030 was really protecting — without forbidding concurrency.

**Reversibility.** High. Toggle workflows off in `/config`; revert to serial primary-session builds. No data migration. The discipline subsection and this entry document the boundary so re-tightening is a one-edit change.

**What does NOT change.** The single concurrent UI-session rule; the bounded-codegen budget (~100 lines per component, now enforced per-agent); MOCK_LLM discipline; human gates blocking; version pins; the prohibition on continuous-running orchestrators and live Polymarket trading.

**First application.** Loop v1 build (full v5 loop: steps 1.5 / 2.5 / 5 / 8) — a Build (parallel) → Integrate (serial) → Verify workflow. See `human/sessions/2026-06-05.md` and `.claude/plans/elegant-bouncing-gem.md`.
