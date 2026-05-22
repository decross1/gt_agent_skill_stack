# Agent System

A portable agent framework — skills + memory — that runs unchanged in **Pi** and
**Claude Code**. Authored once against the [Agent Skills standard](https://agentskills.io);
each harness reads the same files via symlinks (see `README.md`).

This file is the stable context both harnesses load on start. Keep it **small and
stable** — detail belongs in skills (loaded on demand) and in `memory/` (loaded
when relevant), not here.

## Skills

Located in `.agents/skills/`, each a `SKILL.md`. Every skill carries two
frontmatter fields — `layer` (A/B/C) and `runtime-safe` (true/false) — placing
it in one of three layers.

### Layer A — Core discipline

Domain-agnostic execution discipline: the framework's reusable core. These five
are the **runtime-safe core** (`runtime-safe: true`) — designated safe to embed
in autonomously spawned / runtime agents, not only dev-time sessions. The
`runtime-safe` contract they must satisfy is defined in `BOUNDARY.md`; per-skill
conformance is verified in Phase 3.

| Skill | Purpose |
|---|---|
| `resume-state` | Resume a plan-driven project from its state file; find the next task, honor gates. |
| `gate-check` | Halt at human gates / human-only tasks / irreversible actions before acting. |
| `validate` | Run validations as independent pass/fail checks; never coerce a near-miss. |
| `fallback` | Switch to a declared alternative — explicit, time-capped, logged. |
| `run-log` | Append a structured JSONL entry per executed step — append-only, auditable. |

### Layer B — Research & build vertical

A vertical pack for research / ML-pipeline engineering. Dev-time only
(`runtime-safe: false`).

| Skill | Purpose |
|---|---|
| `plan-research` | Design a falsifiable plan: hypothesis, baseline, metric, smallest experiment. |
| `investigate` | Evidence-based debugging via a hypothesis tree — no guess-and-patch. |
| `code-review` | Pre-merge review of a diff, including research-specific risks. |
| `health` | Whole-project checkup with a prioritized status dashboard. |
| `ship` | Mechanical last mile: test, commit, PR, record the decision. |
| `experiment` | Log a single run to the ledger (config, seed, data, metrics). |
| `auto-experiment` | Run an unattended sequence of experiments under a fixed budget. |
| `repro-check` | Gate a result on reproducibility before it is trusted. |

### Layer C — Orchestration & meta

Coordination and framework-internal skills. Dev-time only (`runtime-safe: false`).

| Skill | Purpose |
|---|---|
| `orchestrate` | Decompose a multi-role task, delegate to agent profiles, reconcile. |
| `harvest` | Score the framework's own skills against a consumer project's execution trace. |
| `context-save` | Persist a session handoff to durable memory. |
| `context-restore` | Rebuild context at the start of a session. |

Two working modes:
- **Plan execution** (a contract-governed program): `resume-state` →
  `gate-check` → execute task → `validate` → `run-log`, repeating.
- **Research & build**: `plan-research` → `experiment` → `repro-check` →
  `code-review` → `ship`; `investigate` and `health` as needed.

Use `context-restore`/`context-save` for projects without a formal plan;
`resume-state` for those that have one.

## Agents

Profiles in `.agents/agents/` — named **dev-time** agents, each a role scoped to
a subset of the skills. The `orchestrate` skill decomposes a multi-role task and
routes its parts to these agents.

| Agent | Role | Leans on |
|---|---|---|
| `planner` | Decompose, sequence, design falsifiable plans | `plan-research`, `resume-state`, `gate-check` |
| `builder` | Write, debug, and land code | `investigate`, `code-review`, `ship` |
| `experimenter` | Run and log experiments | `experiment`, `repro-check`, `run-log` |
| `auditor` | Independently verify work and project health | `validate`, `repro-check`, `health`, `gate-check` |

These coordinate the agents that *help build* a project — they are not a
project's own runtime agents. See `BOUNDARY.md`.

## Memory

File-based and harness-agnostic — these files are the shared substrate so
nothing is lost moving between Pi and Claude Code. Pi's runtime `retain`/`recall`
and Claude Code's memory tool operate *on top* of these; the files are canonical.

| File | Role |
|---|---|
| `memory/DECISIONS.md` | **Append-only, date-stamped** log of decisions and corrections. |
| `memory/experiments.md` | Ledger of experiment runs, newest first. |
| `memory/feedback.jsonl` | Append-only ledger of `harvest` findings — consumer-trace evidence about the skills. |
| `memory/conformance.md` | Per-skill conformance dashboard, updated by `harvest`. |
| `memory/session-latest.md` | Transient handoff snapshot — overwritten each session. |
| `memory/projects.md` | Registry of projects on this machine (see Roadmap). |

The framework runs its own development as a plan-driven project — `plan.md` with
`run_state/framework.state.json` and `run_state/framework.run.jsonl`. It dogfoods
its own Layer-A skills.

## Conventions

- Start a session with `resume-state` (plan-driven projects) or
  `context-restore`; end it with `context-save`.
- A human gate is blocking — `gate-check` before any consequential or
  irreversible action; never clear a gate without explicit human action.
- Validations are independent checks; a near-miss is a fail. Never coerce.
- Log every executed step via `run-log` — append-only, observed not intended.
- Every research result passes `repro-check` before it is trusted or shipped.
- `DECISIONS.md` is append-only — never rewrite history; date-stamp new entries.
- Prefer the smallest experiment that could disprove a hypothesis.
- Never `ship` with failing or hidden tests.

When the framework is used inside a project that has its own `AGENTS.md` /
`CLAUDE.md` contract, that contract is authoritative — these skills complement
it; they do not override it.

## Scope boundary

This framework is primarily a **dev-time harness** — it helps a human build
projects. The word "orchestrator" names two systems that must not be conflated:

- **Dev-time** (this framework) — Claude Code / Pi helping build code.
- **Runtime** (the project's own) — the project's own deployed agent system.

**Rule.** Skills fall in two classes. **Dev-only skills** (Layers B and C) must
never be loaded into any project's runtime agent. The **runtime-safe core** (the
5 Layer-A skills) may be *deliberately* embedded in a spawned / runtime agent —
never inherited by accident. The leak vector is the global `~/.pi/agent/skills/`
directory; a project whose runtime runs on Pi must pin its own skill discovery.
Full policy, the `runtime-safe` contract, and verification steps in `BOUNDARY.md`.

## Roadmap

The intended end state is a system that understands **all projects on this
machine** — installed globally (`install.sh --global`) so the skills are
available everywhere, with `memory/projects.md` as a cross-project index. Today
that file is a manually maintained registry; future work is to populate and
refresh it automatically.
