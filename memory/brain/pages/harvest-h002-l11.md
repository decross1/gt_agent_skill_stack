---
slug: "harvest-h002-l11"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-validate", dst_type: "skill"}
---

# H002 — validate:friction

_week1.run.jsonl L14,L21,L48,L51_

**Source skill:** `validate`

**Class:** friction

**Ref:** week1.run.jsonl L14,L21,L48,L51

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi repeatedly finds the declared pass_signal itself mis-specified: L14 a cgroup grep string, L21 a 'FLASHINFER_CUTLASS' log line that encodes a false hardware assumption, L48 a chroma 'default port' that collides with vLLM, L51 a needle 0.85 bar unreachable for the scaffold. validate assumes the criterion is correct and only the result is in question; it has no protocol for 'the check itself is wrong'.

**Plan candidate:** validate: add a protocol for a mis-specified criterion — verify the underlying intent, report the criterion as buggy, never silently coerce or silently substitute.

## Links

- **about** → `skill-validate` (skill)
