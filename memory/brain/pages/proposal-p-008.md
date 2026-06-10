---
slug: "proposal-p-008"
type: "proposal"
date: "2026-06-09"
source: "memory/brain/proposals.jsonl"
edges:
  - {type: targets, dst: "skill-run-log", dst_type: "skill"}
---

# P-008 — Adopt run-log `agent` attribution in a_bgt_rsi (reconcile inviolate rule 6) so unattended multi-agent runs are reconstructible

_agent: claude-code-main_

**Verdict:** `open`

**Target:** skill → `run-log`

**Change:** Consumer-side adoption of the post-S24a run-log schema (framework FR-003): (1) amend a_bgt_rsi inviolate rule 6 to ADD a required `agent` field and accept optional `skill_used` — the 6-field schema becomes a minimum, not a ceiling; (2) emit two first-class run.jsonl entries per Dynamic-Workflow build agent (start + finish), each carrying agent='workflow:wf_xxx/<role>'; (3) record the bump in DECISIONS.md (both repos) linking framework commit 2690b5b. Framework side already shipped: run-log SKILL.md requires `agent`, rules.md FR-003 codifies it, the projector reads it at ingest. HUMAN-GATED: rule 6 is inviolate -> requires human attestation (see handoffs/2026-06-09-a_bgt_rsi-skill-invocation-handoff.md, P0 item 2).

**Reasoning:** 2026-06-09 skill-alignment review (28/31 held): consumer run-log has `agent` populated 0/1004 and the 12 Dynamic-Workflow rows are anonymous (all agent:None, week1.run.jsonl L886-981), so an unattended D-040 Nara workflow's limbs are not reconstructible — you see that the workflow ran, not which agent did what or where a step failed. D-037 rule 5 already asks for per-agent start+finish entries; this closes the gap before D-040 autonomy. Corrects the review's own briefing error: there is NO pre-existing proposal (the cited prop-82537922 does not exist) — this is the first. Routed to human-review: it edits an inviolate consumer rule.

**References:** `run-log`, `rules.md:FR-003`, `a_bgt_rsi/CLAUDE.md:151`, `2690b5b`, `handoffs/2026-06-09-a_bgt_rsi-skill-invocation-handoff.md`

## Links

- **targets** → `skill-run-log` (skill)
