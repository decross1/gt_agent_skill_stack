---
slug: "spawn-sp-001"
type: "spawn"
date: "2026-05-25"
source: "run_state/spawn.jsonl"
edges:
  - {type: uses, dst: "skill-validate", dst_type: "skill"}
  - {type: uses, dst: "skill-run-log", dst_type: "skill"}
---

# SP-001 — count_brain_edges

_status: completed_

**Status:** `completed`

**Parent task:** `s21_5_worked_mock_spawn`

**Child task:** `count_brain_edges`

**Task statement:** Count typed edges in memory/brain/edges.jsonl; report the integer count and the breakdown by edge type.

**Done condition:** Result.child_summary parses as JSON with keys {count:int>=0, by_type:object}; sum(by_type.values()) == count; every key in by_type is in {derived_from, produced, linked_to, falsified_by, supersedes, references}.

**Skill subset:** `validate`, `run-log`

**Authority cap:** Read-only on memory/brain/edges.jsonl. No writes outside its own run-log entry. No network. No shell command other than read.

**Budget:** wall_time=60s iterations=None cost_usd=None

**Done condition check:** `pass`

**Child summary:** {"count":5,"by_type":{"derived_from":1,"produced":1,"falsified_by":1,"references":1,"linked_to":1},"sampled_examples":["experiment-day4-tool-call-rate -derived_from-> hypothesis-day4-tool-call-rate","anomaly-tool-call-100pct <-references- dec-fw-2026-05-24-treat-100-metrics-in-small-n"]}

## Links

- **uses** → `skill-validate` (skill)
- **uses** → `skill-run-log` (skill)
