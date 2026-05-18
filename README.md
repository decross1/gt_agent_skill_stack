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
├── install.sh           wires the system into Pi and/or Claude Code
├── .agents/skills/      canonical skills  (.claude/skills → symlink)
│   ├── plan-research/   falsifiable research planning
│   ├── investigate/     evidence-based debugging
│   ├── review/          pre-merge diff review
│   ├── health/          whole-project checkup
│   ├── ship/            test → commit → PR
│   ├── experiment/      log a run to the ledger
│   ├── repro-check/     reproducibility gate
│   ├── context-save/    persist a session handoff
│   └── context-restore/ rebuild context on resume
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

Typical research loop: `plan-research` → `experiment` → `repro-check` →
`review` → `ship`, with `investigate` and `health` as needed. Begin a session
with `context-restore` and end it with `context-save`.

## Memory

File-based and harness-agnostic, so nothing is lost moving between Pi and Claude
Code. Pi's runtime `retain`/`recall` and Claude Code's memory tool work on top
of these files; the files are canonical. `DECISIONS.md` is append-only.

## Roadmap

End state: machine-wide project awareness — skills installed globally with
`memory/projects.md` as a cross-project index, eventually refreshed
automatically. See `AGENTS.md` for current conventions.
