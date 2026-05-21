---
name: orchestrate
layer: C
runtime-safe: false
description: Decompose a larger task and delegate its parts to specialized dev agents. Use when a task spans planning, building, experimenting, and verification — it splits the work, routes each part to the right agent profile, sequences the hand-offs, and reconciles the results.
---

# orchestrate

Run a multi-step task as a small team rather than one undifferentiated agent.
Each part goes to the agent profile built for it; this skill is the conductor.

This is a **dev-time** skill — it orchestrates the agents that help build a
project. It is not a project's own runtime orchestrator. See `BOUNDARY.md`.

## When to use

A task that genuinely spans roles — e.g. "design, build, and validate feature
X". For single-role work, invoke the skill or agent directly; orchestration
overhead is not free.

## Agent profiles

Defined in `.agents/agents/`. Each profile is a role with a scoped set of skills:

| Agent | Role | Leans on |
|---|---|---|
| `planner` | Decompose, sequence, design falsifiable plans | `plan-research`, `resume-state`, `gate-check` |
| `builder` | Write, debug, and land code | `investigate`, `code-review`, `ship` |
| `experimenter` | Run and log experiments | `experiment`, `repro-check`, `run-log` |
| `auditor` | Independently verify work and project health | `validate`, `repro-check`, `health`, `gate-check` |

## Procedure

1. **Decompose** — break the task into parts, each cleanly owned by one agent
   profile. Name the part, its owner, and its done-condition.
2. **Sequence** — order the parts; mark dependencies. Planning precedes
   building; building precedes auditing. Identify parts that can run in
   parallel.
3. **Gate-check the plan** — before dispatching, run [[gate-check]]. If the task
   crosses a human gate or an irreversible action, halt there.
4. **Delegate** — hand each part to its agent with: the goal, the inputs, the
   done-condition, and the relevant context. Do not hand an agent work outside
   its profile.
5. **Reconcile** — collect each agent's result. Verify the done-condition was
   actually met (not just claimed). A part that fails its check goes back to
   its agent or escalates — it is not waved through.
6. **Log** — record the orchestration (parts, owners, outcomes) via [[run-log]];
   durable decisions to `memory/DECISIONS.md`.

## Rules

- One part, one owner. Overlapping ownership produces conflicting work.
- The orchestrator does not do the parts itself — it routes and reconciles. If
  tempted to "just do this part quickly", that is a sign the decomposition is
  wrong.
- Independent verification stays independent: the `auditor` checking a `builder`'s
  work must not be the same pass that produced it.
- A reconciled result is only done when its done-condition is verified.

## Hand-off

End-of-session state via [[context-save]]; resume via [[context-restore]] or
[[resume-state]]. Agent profiles are the *what*; the skills they use are the
*how*.
