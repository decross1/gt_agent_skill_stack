---
name: spawn-contract
layer: A
runtime-safe: true
pack: core
description: Spawn an autonomous child agent under an explicit, bounded contract. Use when a parent agent (dev-time or runtime) hands a task to a child that will execute without a human in the loop — captures task statement, done-condition, skill subset, authority cap, budget, self-gating rules, reporting format, and escalation path into one durable record before the child is launched.
---

# spawn-contract

Make autonomous spawning *governed*, not improvised. The failure mode this
prevents is the **unbounded child** — an agent dispatched with a vague brief,
no budget, no skill cap, and no declared done-condition, that wanders off,
takes irreversible actions outside its authority, or runs for ten times its
budget while no one notices.

A spawn is legitimate only when its **contract is written *before* the child
runs**. Once written, the contract is immutable; a change is a new spawn.

This skill is the **parent's discipline**. The child does not invoke
spawn-contract — the child uses its own embedded runtime-safe core
([[gate-check]] / [[validate]] / [[run-log]] / [[fallback]] /
[[resume-state]]) under the contract's constraints.

## When to use

Before dispatching any child agent that will execute without a human
between the dispatch and the report-back. This covers, harness-agnostically:

- A dev-time agent launching a sub-agent for autonomous execution.
- A runtime agent spawning a worker for a bounded task.
- A long-running background process that will report back asynchronously.

The spawn mechanism — how the child is actually launched — is the
harness's concern (subprocess, RPC, queue, native sub-agent primitive,
etc.). This skill prescribes the *contract*, not the launcher.

Skip when the "child" is just an inline tool call (file read, grep) —
those are not autonomous and need no contract.

## The contract

Append events to the project's spawn ledger (default:
`run_state/spawn.jsonl`, append-only — same model as [[run-log]] and
the brain's `proposals.jsonl`). One spawn produces **multiple lines
sharing a `spawn_id`**: the initial spawn event holds the full
contract; subsequent events update `status` and add the `result`
block. Latest-status-per-`spawn_id` is the canonical view of the
spawn. The contract block itself is **immutable** once first written —
a change is a new spawn (new `spawn_id` with optional
`supersedes_spawn_id`). Required shape:

```json
{
  "timestamp": "<ISO 8601, spawn time>",
  "spawn_id": "<unique id, e.g. SP-NNN>",
  "parent_task_id": "<task id from run-log that initiated the spawn>",
  "child_task_id": "<id assigned by parent for the child's work>",
  "status": "spawned | running | completed | escalated | aborted | budget_exceeded",
  "contract": {
    "task_statement": "<one paragraph: what the child is to do>",
    "done_condition": "<validate-style spec; how 'done' is checked>",
    "skill_subset": ["resume-state","gate-check","validate","run-log","fallback"],
    "authority_cap": "<declarative: what the child must NOT do; default: no irreversible action without a gate; read-only outside its own log>",
    "budget": {"wall_time_seconds": 600, "iterations": null, "cost_usd": null},
    "self_gating_rules": "<conditions under which the child halts on its own; default: any action outside skill_subset OR authority_cap>",
    "reporting_format": "<channel + shape; default: write child run-log entries; append summary to this entry's `result`>",
    "escalation_path": "<where the child reports if it cannot proceed; default: set status=escalated, leave result.child_summary explaining why>"
  },
  "result": {
    "child_summary": "<filled at completion: child's report-back text>",
    "done_condition_check": "pass | fail | inconclusive",
    "verified_at": "<ISO 8601>",
    "verified_by": "<parent task id that ran reconciliation>"
  }
}
```

## Procedure (parent side)

1. **Define the task fully.** No field in `contract` may be empty at
   write-time. An underspecified contract is a fail-to-launch — fix the
   specification first.
2. **Constrain the skill subset.** Default to the runtime-safe core
   only. Extending beyond it requires an explicit `decision-log` entry
   recording who authorized which extra skill and why.
3. **Set a real budget.** "Wall time" is a hard cap, not aspirational.
   `iterations` and `cost_usd` are optional but recommended where they
   apply. A spawn with no budget is forbidden by this skill.
4. **Write the contract** — append the spawn entry to the spawn ledger
   with `status: "spawned"`. Until this line is written, do not launch
   the child.
5. **Launch the child.** The launch mechanism is harness-specific
   (subprocess / RPC / queue / native primitive); this skill is
   indifferent to which. Whatever the mechanism, the launch must pass
   the contract to the child — by `spawn_id`, by ledger path, or by
   inlined content — so the child knows its constraints.
6. **Wait or poll** within the budget. Do not silently extend. If the
   budget expires before report-back, set `status: "budget_exceeded"`,
   terminate the child if possible, and escalate.
7. **Reconcile.** When the child reports back (or you time out):
   - Run [[validate]] on the child's claimed result against
     `contract.done_condition` as the criterion.
   - Fill in `result` with the validation verdict and timestamp.
   - Set the final `status`: `completed` (validate=pass) /
     `escalated` (validate=fail or inconclusive on a soft criterion) /
     `aborted` (hard failure or budget exceeded).
8. **Log the closure** — append a [[run-log]] entry referencing
   `spawn_id` so the parent's execution trace stays consistent.

## Rules

- **Contract before launch.** Writing the contract precedes the spawn.
  A child that runs before a contract is recorded is unaccounted for —
  treat it as if it had not happened.
- **Contract is immutable.** Once written, no field is edited. A
  needed change is a new spawn entry with a new `spawn_id` that
  references the prior one via `supersedes_spawn_id`.
- **Budget is real.** No silent extension. Cap exceeded → escalate,
  do not "just five more seconds" the way [[fallback]]'s primary path
  is not allowed to limp on past its cap.
- **No self-extending authority.** The child cannot exceed
  `authority_cap`; if it needs more, it escalates and a new contract
  is written.
- **Validate the done-condition.** A spawn cannot be declared
  completed without [[validate]] reporting pass on
  `contract.done_condition`. Wishful-thinking closure is forbidden.
- **Skill subset is closed.** A child whose contract says
  `skill_subset: [run-log, validate]` cannot invoke `fallback` — even
  if its situation seems to need it. The contract is the limit.

## Pairing

[[run-log]] for parent + child execution traces; [[validate]] for the
done-condition check at reconciliation; [[gate-check]] for any gated
action either side encounters; [[fallback]] for the parent's behavior
if the spawn itself fails (e.g. the harness refuses the launch).

[[orchestrate]] is the dev-time multi-role complement — a human in the
loop deciding how to slice and dispatch work across agent profiles.
`spawn-contract` is the autonomous-spawn equivalent: no human between
dispatch and report.
