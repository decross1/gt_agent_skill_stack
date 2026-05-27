---
slug: "harvest-h003-l29"
type: "harvest_finding"
date: "2026-05-22"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-repro-check", dst_type: "skill"}
---

# H003 — repro-check:friction

_week1.run.jsonl L90 task=day5_block2_pipeline_implementation_

**Source skill:** `repro-check`

**Class:** friction

**Ref:** week1.run.jsonl L90 task=day5_block2_pipeline_implementation

**Source project:** a_bgt_rsi

**Evidence:** An embed run was silently stubbed because MOCK_LLM=1 leaked into the main session env; the fake result was caught only by a WARNING log and a suspiciously-fast 1.1s runtime (vs ~57s real), then deleted and redone. repro-check covers seeds, data, environment, and provenance but has no explicit check that the run executed the real thing rather than a mock/stub.

**Plan candidate:** repro-check: add a check that the result came from the real pipeline, not a mock — verify no mock/stub env flag was active and runtime/output is consistent with a genuine run.

## Links

- **about** → `skill-repro-check` (skill)
