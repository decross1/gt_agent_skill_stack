---
slug: "harvest-h002-l20"
type: "harvest_finding"
date: "2026-05-21"
source: "memory/feedback.jsonl"
edges:
  - {type: about, dst: "skill-ship", dst_type: "skill"}
---

# H002 — ship:friction

_week1.run.jsonl L33,L69_

**Source skill:** `ship`

**Class:** friction

**Ref:** week1.run.jsonl L33,L69

**Source project:** a_bgt_rsi

**Evidence:** a_bgt_rsi has no unified test runner (no pytest.ini); tests run as per-day enumerated commands ('.venv/bin/python -m pytest', day-specific test sets). ship step 2 ('run the full test suite using the project's own command') assumes one command exists.

**Plan candidate:** ship + health: handle projects with no unified runner — accept a per-unit enumerated test set as 'the suite'.

## Links

- **about** → `skill-ship` (skill)
