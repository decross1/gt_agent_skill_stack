---
slug: "harvest-h005-l31"
type: "harvest_finding"
date: "2026-05-24"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-run-log", dst_type: "skill"}
---

# H005 — run-log:diverged

_week1.run.jsonl L131 task=rectify_malformed_run_log_lines_

**Source skill:** `run-log`

**Class:** diverged

**Ref:** week1.run.jsonl L131 task=rectify_malformed_run_log_lines

**Source project:** a_bgt_rsi

**Evidence:** L131 EDITED 4 prior Day-6 run.jsonl entries (L99, L105, L106, L109) to escape unescaped inner double quotes that broke JSONL parsing — violates run-log's 'Append only. Never edit or delete a past entry' rule. The consumer handled it per its own inviolate-rule-5 (Track A is the rectifier), retained a backup (week1.run.jsonl.pre-rectify-bak), and verified 0 malformed across the rectified file before deleting the backup at Day-8 cleanup. The break was structural (JSONL parse failure broke a UI integrity test), not semantic. The framework's rule says 'a correction is a new entry that references the old one' — but a malformed JSONL line cannot be referenced by id because it isn't parseable.

**Plan candidate:** run-log: explicit carve-out for STRUCTURAL rectification of malformed entries (with backup + attestation + the rectifying entry itself logged); rule for SEMANTIC corrections (new-entry-references-old) stays unchanged.

## Links

- **about** → `skill-run-log` (skill)
