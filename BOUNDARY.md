# Scope boundary

The framework helps build projects (**dev-time**). It must not entangle itself
with a project's own deployed agents (**runtime**) — *except* through one
deliberate channel: a small **runtime-safe core** designed to be embedded. This
document draws that line.

## Two orchestrators, one word

"Orchestrator" names two different systems. They must not be conflated.

| | Dev-time harness (this framework) | Project runtime (the project's own) |
|---|---|---|
| **What** | Claude Code / Pi helping a human build a project | The project's own deployed agent system |
| **Job** | Plan, write, review, ship the code | Do the project's actual work |
| **Lives** | The developer's machine, dev sessions | Inside the project, often sandboxed |
| **Example** | This framework in a Claude Code session | `a_bgt_rsi`'s Gemma 4 + OpenClaw stack, in its sandbox |

A developer's `code-review` skill has no business running inside a project's
production loop. But a project's runtime agent *does* need discipline — gating,
validation, logging — and that discipline is general. Hence **two classes of
skill**, not one blanket ban.

## Two skill classes

Every skill carries a `layer` and a `runtime-safe` frontmatter field.

**Dev-only skills — Layers B and C** (`runtime-safe: false`). The research
vertical (`plan-research`, `investigate`, `code-review`, `health`, `ship`,
`experiment`, `auto-experiment`, `repro-check`) and the orchestration / meta
layer (`orchestrate`, `harvest`, `context-save`, `context-restore`). These help
a human *build* a project.

> **Rule.** Dev-only skills must never be loaded into any project's runtime
> agent. They assume a developer, a dev harness, and a build task.

**Runtime-safe core — Layer A** (`runtime-safe: true`). The five
execution-discipline skills: `resume-state`, `gate-check`, `validate`,
`run-log`, `fallback`. Domain-agnostic, and designed to be embedded in an
autonomously spawned or runtime agent — that is what the designation means.

> **Rule.** A runtime agent may include the runtime-safe core *by deliberate
> choice*. It must never *inherit* it — or any dev-only skill — by accident.

This supersedes the earlier blanket "all skills are dev-time only" rule
(2026-05-18). The line did not move; it sharpened — from "all skills" to "the
dev-only layers."

## The runtime-safe contract

A skill is `runtime-safe: true` only if it satisfies all of:

1. **No assumed human.** It works with no human in the loop. Where a dev-time
   skill says "halt and print for a human," the runtime-safe behaviour is to
   emit a structured blocked / needs-attention status and stop — not to wait at
   a prompt.
2. **No dev-harness dependency.** No PRs, no assumed git workflow, no
   Claude-Code- or Pi-specific tooling. It depends only on a state file, a log,
   and plain file I/O.
3. **Minimal context cost.** A runtime agent has a tight context budget; a
   runtime-safe `SKILL.md` stays terse and self-contained.
4. **No surprising side effects.** Its only writes are to its own declared log
   or state file. It never takes an irreversible action without a gate.
5. **Closed dependency set.** It references only other runtime-safe skills.

Layer A skills are *designated* runtime-safe as of `plan.md` Session 5. Per-skill
conformance to this contract is verified and hardened in Phase 3; until a skill
passes that check, an embedder treats it as designated-but-not-yet-verified.

## The leak vector

Pi discovers skills from several directories, including the global
`~/.pi/agent/skills/`. A project whose runtime also runs on Pi, on the same
machine, can inherit whatever is there.

- A **dev-only** skill inherited into a runtime agent is a defect — extra skill
  descriptions in a minimal-context agent, and a risk of a spurious invocation
  of a build-time skill in a production loop.
- A **runtime-safe** skill inherited *by accident* is still wrong — not because
  the skill is unsafe, but because accidental composition is not deliberate
  composition. A runtime agent's skill set must be a decision, not a leftover.

`install.sh --global` installs for Claude Code only and does not touch Pi.
`install.sh --global-pi` is the explicit, warned opt-in. The default keeps the
leak closed.

## Keeping the line

**On this framework's side:**
- `install.sh --global` installs for Claude Code only; `--global-pi` is the
  explicit, warned opt-in; `--uninstall` removes every global symlink cleanly.

**On the project's side** (the project owns this):
- A project whose runtime runs on Pi must **pin its own skill discovery** —
  point its runtime at a project-local skill directory and do not let it inherit
  `~/.pi/agent/skills/`.
- If the project's runtime wants discipline, it **deliberately vendors the
  runtime-safe core** into its own skill set — it does not rely on inheritance.

## Verification check

Run on the dev machine:

```sh
# Where are the dev skills installed?
ls -la ~/.claude/skills ~/.pi/agent/skills 2>/dev/null

# Does any project carry a Pi skill dir that would shadow/inherit?
find ~/projects -maxdepth 3 \( -name '.pi' -o -name '.agents' \) -type d 2>/dev/null
```

Before a project's runtime goes live, confirm its runtime agent's skill list
contains **only**: the project's own skills, plus — if deliberately chosen — the
runtime-safe core. It must contain **no** Layer-B or Layer-C skill.
