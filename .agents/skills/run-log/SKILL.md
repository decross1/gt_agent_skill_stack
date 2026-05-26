---
name: run-log
layer: A
runtime-safe: true
pack: core
description: Append a structured JSONL entry recording an executed step. Use after running any plan task, experiment, validation, or significant action that should be auditable — captures timestamp, identity, status, observed vs expected, and duration to an append-only log.
---

# run-log

Make execution auditable. Every consequential step leaves one structured line in
an append-only log, so a run can be reconstructed, resumed, and trusted after the
fact. An unlogged step is a step that did not provably happen.

## When to use

After executing a plan task, after a [[validate]] check, after a [[gate-check]]
halt, on a state transition, and whenever a fallback or non-default path is
taken. Logging is not optional — a task is not done until its entry is written.

## Entry shape

Append one JSON object per line (JSONL) to the project's run log. Use the
project's own schema if it defines one; otherwise this default:

```json
{
  "timestamp": "<ISO 8601>",
  "task_id": "<identifier of the step>",
  "status": "started | passed | partial_pass | failed | aborted | halted | escalated | skipped",
  "observable_expected": "<what success was defined as>",
  "observable_actual": "<what was observed>",
  "duration_ms": <integer>,
  "notes": "<optional: fallback taken, gate reached, deviation>"
}
```

State transitions and fallback selections get their **own** entries, not a note
buried in another task's line.

## Status values

The enum above is a default that fits typical plan-execution; a project may
extend it, but each value should mean exactly one thing.

- **`started`** — execution began. Used as a separate entry when start time
  matters (a long-running step) or when a step may be interrupted.
- **`passed`** — done; the declared criterion ([[validate]]) was met.
- **`partial_pass`** — done; the work itself is correct, but a declared
  criterion was mis-specified, reported as a finding, and escalated. Allowed
  only in the narrow sense [[validate]] defines — never as a softer word for a
  failed run.
- **`failed`** — done; the declared criterion was not met. The reason lives in
  `observable_actual`, not edited or relabelled.
- **`aborted`** — execution stopped because a hard checkpoint failed; the
  larger unit of work is on hold pending decision.
- **`halted`** — execution stopped at a gate; see [[gate-check]].
- **`escalated`** — execution paused and surfaced to a human, typically for a
  mis-specified criterion or an ambiguous outcome. Differs from `halted` in
  that the issue is in the criterion or interpretation, not a pre-declared
  gate.
- **`skipped`** — not executed (e.g. a fallback branch took the step off the
  path). Log it anyway, with the reason.

## Rules

- **Append only.** Never edit or delete a past entry. A correction is a new
  entry that references the old one.
- **Log the failure too.** A non-passing step — `failed`, `aborted`, `halted`,
  `escalated`, `partial_pass`, `skipped` — is logged with the same rigor as a
  passing one. That is the point of the log.
- **Observed, not intended.** `observable_actual` records what happened, even
  when it diverges from the plan. The log is evidence, not a narrative.
- A fallback or time-cap breach is always its own logged event.

## Pairing

Read at session start by [[resume-state]] to reconstruct progress. The durable
*decisions* that emerge still go to `memory/DECISIONS.md`; experiment outcomes
to the [[experiment]] ledger. The run log is the fine-grained execution trace
beneath both.
