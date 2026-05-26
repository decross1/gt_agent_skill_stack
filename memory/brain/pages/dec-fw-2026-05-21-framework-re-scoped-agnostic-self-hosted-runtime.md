---
slug: "dec-fw-2026-05-21-framework-re-scoped-agnostic-self-hosted-runtime"
type: "decision"
date: "2026-05-21"
source: "memory/DECISIONS.md"
---

# 2026-05-21 — Framework re-scoped: agnostic, self-hosted, runtime-safe core

_framework decision_

**Decision:** The framework is re-scoped from an ML/research-tuned toolkit to an
*agnostic* framework for disciplined agentic development and autonomously spawned
agents, usable by any system. `a_bgt_rsi` remains the lead consumer that informs
it. Three structural commitments, ratified in `plan.md` (v1):
1. **Dogfooded** — the framework's own development runs as a plan-driven project
   using its own skills (`plan.md` + `run_state/framework.state.json` +
   `run_state/framework.run.jsonl`).
2. **Read-only feedback** — a `harvest` skill scores each skill against
   `a_bgt_rsi`'s execution trace into `memory/feedback.jsonl`; `a_bgt_rsi` itself
   is never modified.
3. **Runtime-safe core** — a subset of Layer-A skills will become embeddable in
   spawned/runtime agents; `BOUNDARY.md`'s blanket dev-time-only ban becomes a
   layering rule (scheduled for Session 5).
**Why:** The framework was a high-fidelity mirror of one project's discipline but
had no falsifiable claim about its own value, no feedback loop, and a
"research-tuned" identity that contradicted the goal of general use. `plan.md`
gives it a charter, metrics, decision rules, and a 20-session improvement arc.
**Supersedes:** revises the scope of the 2026-05-18 "Agent system scaffolded"
decision. The 2026-05-18 "Scope boundary" decision stands until Session 5
formally rewrites `BOUNDARY.md`.
