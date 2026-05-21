# Decisions Log

Append-only, date-stamped record of decisions and corrections. **Never rewrite or
delete entries** — add new ones. Newest at the bottom. Each entry: what was
decided, why, and (if it supersedes an earlier one) which.

Format:

```
## YYYY-MM-DD — <short title>
**Decision:** ...
**Why:** ...
**Supersedes:** <date/title, or "none">
```

---

## 2026-05-18 — Agent system scaffolded
**Decision:** Created a portable agent framework (skills + file memory) authored
to the Agent Skills standard, runnable in both Pi and Claude Code via symlinks.
Adopted a curated, research-tuned subset of gstack rather than the full
product-oriented framework.
**Why:** Target harness is Pi; current harness is Claude Code; the project
(`autoresearch`) is an ML/research pipeline with no product-UI dimension, so
gstack's CEO/design/QA-browser roles do not apply.
**Supersedes:** none

## 2026-05-18 — Added execution-discipline skills
**Decision:** Added 4 skills — `gate-check`, `validate`, `run-log`,
`resume-state` — and adapted `experiment` (autonomous loop section) and
`plan-research` (design-vs-execute pointer).
**Why:** Explored the primary consumer `/home/decross1/projects/a_bgt_rsi` — a
contract-governed, plan-driven research program (authoritative `plan.yaml`,
state-file resume, blocking human gates, JSONL run log, validations never
coerced). The original gstack-derived skills were a design/ship loop and did
not cover plan-execution discipline, which is this project's core need. The
gstack safety roles (`/careful`/`/freeze`/`/guard`) dropped on 2026-05-18 are,
reframed, exactly this gap. Skills stay general-purpose.
**Supersedes:** partially revises the 2026-05-18 scaffold decision's skill set.

## 2026-05-18 — Scope boundary: dev-time vs project-runtime
**Decision:** Established that this framework is a dev-time harness only; its
skills must not be loaded into any project's runtime agent. Added `BOUNDARY.md`
and a `## Scope boundary` section to `AGENTS.md` / `README.md`.
**Why:** Explored `a_bgt_rsi`'s architecture — its runtime orchestrator (Gemma 4
+ OpenClaw + NemoClaw) also runs on Pi. With the dev skills installed globally
in `~/.pi/agent/skills/`, the apparatus runtime could inherit them. The two
"orchestrators" (dev-time and apparatus-runtime) must stay separate.
**Supersedes:** none

## 2026-05-21 — Correction: the lead consumer is `a_bgt_rsi`, not `autoresearch`
**Decision:** The 2026-05-18 "Agent system scaffolded" entry names the consumer
project `autoresearch`. That is incorrect: `autoresearch` is a third-party repo
cloned *inside* `a_bgt_rsi` (`a_bgt_rsi/clones/autoresearch`). The framework's
lead consumer is `/home/decross1/projects/a_bgt_rsi`.
**Why:** This log is append-only; the original entry cannot be rewritten. This
entry corrects the record.
**Supersedes:** corrects — does not supersede — the project name in the
2026-05-18 "Agent system scaffolded" entry.

## 2026-05-21 — Framework re-scoped: agnostic, self-hosted, runtime-safe core
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
