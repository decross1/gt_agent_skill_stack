---
slug: "2026-06-10-s2-d050-decision-run"
type: "reflection"
date: "2026-06-10"
source: "memory/brain/narratives.jsonl"
edges:
  - {type: linked_to, dst: "D-050", dst_type: "decision"}
---

# 2026-06-10-s2-d050-decision-run

**Intent:** Execute the D-050 pre-registered battery decision run at the first GPU-idle window and judge the two dark-shipped skeptic seams by the locked rule.

**Did:** Caught the window 3 minutes after S3's soak ended (registry-empty check), ran the full-22 real battery (31 min) with both gates on, judged all four criteria mechanically from the artifact against the 2026-06-09 baseline, recorded FAIL, kept the gates dark, named the two defects, and deliberately did NOT spend the one allowed revision cycle past the session's 2-3h budget.

**Observed:** C1 passed exactly as designed - the boundary case the whole residual-1 effort targeted is now gated, and recall stayed 8/8. The interesting failures: (1) the independent skeptic's domain definition condemned plain-language canonical GT (ultimatum, hawk-dove, folk theorem, quantal lock-in) - an LLM judge asked to attack topicality reads informal phrasing as off-domain; vocabulary-register bias, the mirror image of the camouflage problem R0 was built for. (2) The rule's citation requirement (non-null contradicting_paper_id) caught a wiring bug no test caught: the hook carried verdict provenance but dropped the doc id. A pre-registered rule that reads SPECIFIC fields is also an integration test of the fields themselves.

**Would do differently:** When a decision rule requires a field (contradicting_paper_id), add a hermetic test asserting the producing path populates it - the rule found the gap at the cost of a 31-minute real run instead of a 0.1s test. And when prompting an adversarial domain judge, include plain-language in-domain exemplars from day one; register bias was predictable.

**Corrections honored:** D-045, D-050, inviolate-rule-4, inviolate-rule-7

## Links

- **linked_to** → `D-050` (decision)

## Referenced by

- `agent-claude-code-main` (agent) — **authored**
