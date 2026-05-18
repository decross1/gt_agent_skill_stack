# Scope boundary

This framework is a **dev-time harness**. It must not entangle itself with the
**runtime** of any project it helps build. This document draws that line and
says how to keep it.

## Two orchestrators, one word

The word "orchestrator" names two different systems. They must not be conflated.

| | Dev-time harness (this framework) | Apparatus runtime (the project's own) |
|---|---|---|
| **What** | Claude Code / Pi helping a human build a project | The project's own deployed agent system |
| **Job** | Plan, write, review, ship the code | Do the project's actual work |
| **Skills** | The 13 skills in `.agents/skills/` | The project's own skill set, if any |
| **Lives** | The developer's machine, dev sessions | Inside the project, often sandboxed |
| **Example** | This framework, in a Claude Code session | `a_bgt_rsi`: Gemma 4 + OpenClaw + NemoClaw, inside the OpenShell sandbox on the DGX Spark |

A developer's `code-review` skill has no business running inside a project's
production research loop. The two are different systems with different jobs.

## The rule

> **These skills are dev-time only. They must not be loaded into any project's
> runtime agent.** A project's runtime agent uses the project's own skill set —
> never this global dev set.

## The leak vector

Both this framework and some projects (e.g. `a_bgt_rsi`) run on **Pi**. Pi
discovers skills from several directories, including the global
`~/.pi/agent/skills/`. `install.sh --global` populates that directory.

So a project whose *runtime* also runs on Pi, on the same machine, could inherit
these 13 dev skills into its runtime context — extra skill descriptions in a
minimal-context agent, and a small risk of a spurious invocation.

## Keeping the line

**On this framework's side:**
- `install.sh --global` is for the *developer's* harnesses. That is its only
  intended scope.
- `install.sh --uninstall` removes every global symlink cleanly.

**On the project's side** (the project owns this — it is documented here so the
guidance travels with the framework):
- A project whose runtime runs on Pi must **pin its own skill discovery** —
  point Pi at a project-local skill directory (`.pi/skills/` or `.agents/skills/`
  within the project) and do not let the runtime inherit `~/.pi/agent/skills/`.
- For `a_bgt_rsi` specifically: when the Day-6 OpenClaw orchestrator is set up,
  give it a dedicated skill set; verify it does not see this framework's skills.

## Verification check

Run on the dev machine to see the current footprint:

```sh
# Where are the dev skills installed?
ls -la ~/.claude/skills ~/.pi/agent/skills 2>/dev/null

# Does any project carry a Pi skill dir that would shadow/inherit?
find ~/projects -maxdepth 3 \( -name '.pi' -o -name '.agents' \) -type d 2>/dev/null
```

Before a project's runtime goes live (for `a_bgt_rsi`, before Day 6): confirm
its runtime agent's skill list contains **only** the project's own skills, not
the names in `agent_system/.agents/skills/`.
