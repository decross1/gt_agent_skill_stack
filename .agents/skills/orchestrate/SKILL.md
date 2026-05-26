---
name: orchestrate
layer: C
runtime-safe: false
pack: meta
description: Decompose a larger task and delegate its parts to specialized dev agents. Use when a task spans planning, building, experimenting, and verification — it splits the work, routes each part to the right agent profile, sequences the hand-offs, and reconciles the results.
---

# orchestrate

Run a multi-step task as a small team rather than one undifferentiated agent.
Each part goes to the agent profile built for it; this skill is the conductor.

This is a **dev-time** skill — it orchestrates the agents that help build a
project. It is not a project's own runtime orchestrator. See `BOUNDARY.md`.

For the **autonomous-spawn case** — when a parent agent (dev-time or
runtime) hands a task to a child that will execute *without a human in
the loop* between dispatch and report — use [[spawn-contract]] instead.
`orchestrate` assumes a human watching the multi-role flow; `spawn-contract`
is the same kind of decomposition but with the human gap closed by an
explicit, bounded, immutable contract written before the child runs.

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
   parallel — run those under the worktree protocol below.
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

## Parallel parts: the worktree protocol

When the decomposition has parts that can run at once (step 2), do not let them
edit the same working tree. Give each parallel part its own **git worktree** and
a **file-boundary allow-list** — the exact paths it may write. This keeps
concurrent work from colliding or merging unreviewed.

1. **One worktree per parallel part.** Each runs in its own `git worktree` on
   its own branch. No two parallel parts share a checkout.
2. **Declare a file-boundary allow-list.** Before a part starts, write down the
   paths it owns. It writes only inside that list; shared files and another
   part's paths are off-limits.
3. **Isolate shared resources.** A part that does not own a scarce or stateful
   external resource (a served model, a database, a live endpoint) uses a mock
   or fixture. Only the owning part touches the real one — and it verifies the
   resource is real, because a stray mock flag left in the environment will
   silently produce fake results.
4. **Require a completion sentinel.** A part is not ready to integrate until it
   says so explicitly — a declared marker (e.g. `PART <name> COMPLETE`) in its
   final commit or hand-off. No sentinel means not done.
5. **Verify the boundary before merging.** Diff the part's branch against the
   integration branch (`git diff --name-only`) and confirm every changed path
   is on that part's allow-list. A path outside it is a blocking finding — the
   merge stops and the part goes back.
6. **Merge deliberately, verify after.** Integrate with a non-fast-forward
   merge (`git merge --no-ff`) so each part lands as one reviewable commit.
   Confirm the merged result matches what was reviewed, then run the sanity
   checks. On a conflict or a failed check, revert the merge — do not patch in
   place.

Roles (above) say *who* owns a part; this protocol says *how* parts run side by
side without corrupting each other's work.

## Rules

- One part, one owner. Overlapping ownership produces conflicting work.
- Parallel parts run in isolated git worktrees, each with a declared
  file-boundary allow-list — never let two parts edit one tree.
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
