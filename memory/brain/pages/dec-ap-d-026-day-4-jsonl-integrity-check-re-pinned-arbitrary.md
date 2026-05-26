---
slug: "dec-ap-d-026-day-4-jsonl-integrity-check-re-pinned-arbitrary"
type: "decision"
date: "2026-05-21"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-026 — Day-4 jsonl-integrity check re-pinned: arbitrary `≥30 total` → per-artifact record counts

_apparatus decision_

**Date locked.** 2026-05-21, Day-5 startup; human-authorized (decross1).
**Decision.** The `day4_end_of_day_artifacts` jsonl-integrity validation
in `plan.yaml` is amended. The bullet `total entries across day 4 ≥ 30`
(with `fail_signal: total < 30`) is replaced by per-artifact record
counts: `logs/day4_e2e.jsonl` has 2 linked records (matching
`parent_request_id`) and `logs/day4_robust.jsonl` has 2 records per
trial (10 for `--n 5`). The `verify_log_integrity(...) == 0` checks on
both logs are unchanged. Day 4 was logged `partial_pass` on this bullet;
with the amendment the prescribed scope satisfies the check and the
finding `state.notes.day_4_entries_count_finding` is resolved/closed.
**Alternatives.**
- Coerce the Day-4 `partial_pass` to a pass without amending the plan —
  rejected: violates Inviolate Rule 4 (validations are never silently
  coerced); the mismatch was correctly reported, not recoded.
- Leave the plan unchanged and accept the `partial_pass` permanently —
  rejected by the human: the threshold is wrong, not the run, and a
  standing wrong bar mis-signals every future reader of the plan.
- Inflate Day-4 activity (extra trials/chains) to reach 30 — rejected
  as gaming: it would manufacture log records solely to clear a bar,
  not reflect the prescribed Day-4 scope.
- Lower the aggregate to a flat `≥18` — rejected: still arbitrary and
  brittle. The day-4 run-log entry count drifts as post-review fixes
  and merges append entries (now ~13 run-log + 12 call records ≈ 25),
  so any aggregate is unstable.
**Rationale.** The original `≥30` anticipated richer Day-4 activity than
the prescription (`--n 5` trials of 2-record chains plus one e2e chain)
can produce — that scope structurally yields exactly 12 call-log
records. The meaningful invariant is not a headcount but that each log
artifact contains exactly the prescribed, well-formed chains. The
per-artifact counts pin that invariant precisely and do not drift with
unrelated run-log appends. Reported on Day 4 as a finding (run log
`task_id=day4_end_of_day_artifacts`, `status=partial_pass`) rather than
coerced; carried as `state.notes.day_4_entries_count_finding` and
resolved here.
**Operational notes.** Edit applied to `plan.yaml`
`day4_end_of_day_artifacts` validation block with an inline amendment
comment pointing to this decision. `state.notes.day_4_entries_count_finding`
updated to mark the carryover resolved. Day 4 stays in `completed_tasks`;
its run-log entry keeps the original `status=partial_pass` (the run log
is append-only history — the resolution is recorded forward, not by
rewriting the past entry).
**Reversibility.** Easy — `git revert` the plan.yaml hunk restores the
`≥30` bullet. The amendment is scoped to one validation bullet on one
already-complete day and touches no version pin, human-only block, or
hard checkpoint.

---
