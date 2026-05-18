# Agent System

A portable agent framework — skills + memory — that runs unchanged in **Pi** and
**Claude Code**. Authored once against the [Agent Skills standard](https://agentskills.io);
each harness reads the same files via symlinks (see `README.md`).

This file is the stable context both harnesses load on start. Keep it **small and
stable** — detail belongs in skills (loaded on demand) and in `memory/` (loaded
when relevant), not here.

## Skills

Located in `.agents/skills/`, each a `SKILL.md`. Tuned for rigorous,
research-style engineering on ML / research pipelines.

**Execution discipline** — for projects that execute a written plan under a
contract with human gates:

| Skill | Purpose |
|---|---|
| `resume-state` | Resume a plan-driven project from its state file; find the next task, honor gates. |
| `gate-check` | Halt at human gates / human-only tasks / irreversible actions before acting. |
| `validate` | Run validations as independent pass/fail checks; never coerce a near-miss. |
| `run-log` | Append a structured JSONL entry per executed step — append-only, auditable. |

**Research & build:**

| Skill | Purpose |
|---|---|
| `plan-research` | Design a falsifiable plan: hypothesis, baseline, metric, smallest experiment. |
| `investigate` | Evidence-based debugging via a hypothesis tree — no guess-and-patch. |
| `review` | Pre-merge review of a diff, including research-specific risks. |
| `health` | Whole-project checkup with a prioritized status dashboard. |
| `ship` | Mechanical last mile: test, commit, PR, record the decision. |
| `experiment` | Log a run to the ledger; includes the autonomous experiment loop. |
| `repro-check` | Gate a result on reproducibility before it is trusted. |
| `context-save` | Persist a session handoff to durable memory. |
| `context-restore` | Rebuild context at the start of a session. |

Two working modes:
- **Plan execution** (a contract-governed program): `resume-state` →
  `gate-check` → execute task → `validate` → `run-log`, repeating.
- **Research & build**: `plan-research` → `experiment` → `repro-check` →
  `review` → `ship`; `investigate` and `health` as needed.

Use `context-restore`/`context-save` for projects without a formal plan;
`resume-state` for those that have one.

## Memory

File-based and harness-agnostic — these files are the shared substrate so
nothing is lost moving between Pi and Claude Code. Pi's runtime `retain`/`recall`
and Claude Code's memory tool operate *on top* of these; the files are canonical.

| File | Role |
|---|---|
| `memory/DECISIONS.md` | **Append-only, date-stamped** log of decisions and corrections. |
| `memory/experiments.md` | Ledger of experiment runs, newest first. |
| `memory/session-latest.md` | Transient handoff snapshot — overwritten each session. |
| `memory/projects.md` | Registry of projects on this machine (see Roadmap). |

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

## Roadmap

The intended end state is a system that understands **all projects on this
machine** — installed globally (`install.sh --global`) so the skills are
available everywhere, with `memory/projects.md` as a cross-project index. Today
that file is a manually maintained registry; future work is to populate and
refresh it automatically.
