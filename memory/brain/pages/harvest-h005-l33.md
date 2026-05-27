---
slug: "harvest-h005-l33"
type: "harvest_finding"
date: "2026-05-24"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-orchestrate", dst_type: "skill"}
---

# H005 — orchestrate:friction

_week1.run.jsonl L133 task=merge_track_d_day7_eod_

**Source skill:** `orchestrate`

**Class:** friction

**Ref:** week1.run.jsonl L133 task=merge_track_d_day7_eod

**Source project:** a_bgt_rsi

**Evidence:** Track D's EOD merge proceeded with 'Sentinel TRACK D COMPLETE present via verbal attestation' — i.e. the human verbally attested completeness in lieu of writing the sentinel file the S7 parallel-worktree protocol mandates. References memory 'sidetrack-sentinel-attestation'. The S7 protocol made sentinels file-only; the dev-time human-in-loop reality finds verbal attestation acceptable when the human is present and acts as gate-check's attestation-cleared mode. The two skills (orchestrate + gate-check) intersect here without explicit guidance.

**Plan candidate:** orchestrate: allow a completion-sentinel to be either (a) the sentinel file, or (b) a logged attestation-cleared mode (cf. [[gate-check]]); make the substitution explicit so it isn't a sidetrack memory.

## Links

- **about** → `skill-orchestrate` (skill)
