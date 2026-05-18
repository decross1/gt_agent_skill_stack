# Agent System

A portable agent framework — **skills + memory** — built to run unchanged in the
[Pi](https://github.com/badlogic/pi-mono) coding agent and in Claude Code. It
adopts a curated, research-tuned subset of [gstack](https://github.com/garrytan/gstack),
shaped for rigorous ML / research-pipeline work rather than product/SaaS development.

## Why it is portable

There is **one source of truth** and no duplication:

- Skills are authored to the [Agent Skills standard](https://agentskills.io)
  (`SKILL.md`) in `.agents/skills/`.
- The context file is `AGENTS.md`.

Pi reads `.agents/skills/` and `AGENTS.md` natively. Claude Code reads
`.claude/skills/` and `CLAUDE.md`. `install.sh` creates symlinks so both names
point at the same files — edit the originals, both harnesses follow.

## Layout

```
agent_system/
├── AGENTS.md            canonical context file  (CLAUDE.md → symlink)
├── BOUNDARY.md          dev-time vs project-runtime scope boundary
├── install.sh           wires the system into Pi and/or Claude Code
├── .agents/skills/      canonical skills  (.claude/skills → symlink)
│   ├── resume-state/    resume a plan-driven project from its state file
│   ├── gate-check/      halt at human gates / irreversible actions
│   ├── validate/        independent pass/fail checks, never coerced
│   ├── fallback/        explicit, time-capped, logged path switching
│   ├── run-log/         append-only JSONL execution log
│   ├── plan-research/   falsifiable research planning
│   ├── investigate/     evidence-based debugging
│   ├── code-review/     pre-merge diff review
│   ├── health/          whole-project checkup
│   ├── ship/            test → commit → PR
│   ├── experiment/      log a single run to the ledger
│   ├── auto-experiment/ unattended experiment loop under a budget
│   ├── repro-check/     reproducibility gate
│   ├── context-save/    persist a session handoff
│   ├── context-restore/ rebuild context on resume
│   └── orchestrate/     decompose + delegate a multi-role task
├── .agents/agents/      dev agent profiles (.claude/agents → symlink)
│   ├── planner.md       decompose, sequence, plan
│   ├── builder.md       write, debug, land code
│   ├── experimenter.md  run and log experiments
│   └── auditor.md       independently verify work
└── memory/
    ├── DECISIONS.md     append-only decisions log
    ├── experiments.md   experiment ledger
    ├── session-latest.md transient session handoff
    └── projects.md      machine-wide project registry
```

## Install

```bash
./install.sh            # project-local: usable inside this repo
./install.sh --global   # also installs skills for every project on this machine
./install.sh --uninstall
```

The script never overwrites a real file — only absent paths or existing symlinks.

## Usage

- **Pi:** open this directory; it picks up `AGENTS.md` and `.agents/skills/`.
  Skills are invoked as `/skill:plan-research`, etc.
- **Claude Code:** after `install.sh`, skills load from `.claude/skills/` (or
  globally) and `CLAUDE.md` is read automatically.

Two working modes:
- **Plan execution** — for a contract-governed program with human gates:
  `resume-state` → `gate-check` → execute task → `validate` → `run-log`.
- **Research & build**: `plan-research` → `experiment` → `repro-check` →
  `code-review` → `ship`, with `investigate` and `health` as needed.

Begin a session with `resume-state` (planned projects) or `context-restore`
(everything else); end with `context-save`.

For a task that spans roles, the `orchestrate` skill decomposes it and delegates
to the agent profiles in `.agents/agents/` (`planner`, `builder`,
`experimenter`, `auditor`) — dev-time agents, see `BOUNDARY.md`.

## Memory

File-based and harness-agnostic, so nothing is lost moving between Pi and Claude
Code. Pi's runtime `retain`/`recall` and Claude Code's memory tool work on top
of these files; the files are canonical. `DECISIONS.md` is append-only.

## Scope boundary

This is a **dev-time harness** — it helps build projects; it is not a project's
own runtime agent. These skills must not be loaded into a project's runtime
(e.g. `a_bgt_rsi`'s sandboxed orchestrator). See `BOUNDARY.md`.

## Roadmap

End state: machine-wide project awareness — skills installed globally with
`memory/projects.md` as a cross-project index, eventually refreshed
automatically. See `AGENTS.md` for current conventions.
