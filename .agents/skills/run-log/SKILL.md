---
name: run-log
layer: A
runtime-safe: true
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
  "status": "passed | failed | aborted | halted | skipped",
  "observable_expected": "<what success was defined as>",
  "observable_actual": "<what was observed>",
  "duration_ms": <integer>,
  "notes": "<optional: fallback taken, gate reached, deviation>"
}
```

State transitions and fallback selections get their **own** entries, not a note
buried in another task's line.

## Rules

- **Append only.** Never edit or delete a past entry. A correction is a new
  entry that references the old one.
- **Log the failure too.** A failed, aborted, or halted step is logged with the
  same rigor as a success — that is the point of the log.
- **Observed, not intended.** `observable_actual` records what happened, even
  when it diverges from the plan. The log is evidence, not a narrative.
- A fallback or time-cap breach is always its own logged event.

## Pairing

Read at session start by [[resume-state]] to reconstruct progress. The durable
*decisions* that emerge still go to `memory/DECISIONS.md`; experiment outcomes
to the [[experiment]] ledger. The run log is the fine-grained execution trace
beneath both.
