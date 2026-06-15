# Handoff — P-008: run-log `agent` attribution (a_bgt_rsi)

_Accepted 2026-06-15 (human:ui) **with amendment**. This is the crisp, final form to
implement in the next `a_bgt_rsi` dev session. It supersedes the auto-generated
`handoffs/P-008.md` (which still shows the pre-amendment "human-gated" wording)._

- **Decision:** P-008 accepted, with the human attestation replaced by an **automated gate**.
- **Target:** `a_bgt_rsi` inviolate **rule 6** (run-log schema) + the run.jsonl emit path.
- **Framework basis:** FR-003 / commit `2690b5b` (the framework already requires `agent`).

## The final proposal (amended)

1. **Amend inviolate rule 6:** ADD a required `agent` field and accept an optional
   `skill_used` field. The 6-field schema becomes a **minimum, not a ceiling**.
2. **Emit two entries per Dynamic-Workflow build agent** — a `start` and a `finish`
   run.jsonl row — each carrying `agent="workflow:wf_xxx/<role>"`.
3. **AUTOMATED-GATE (replaces the old human attestation).** Rule-6 reconciliation is
   verified by a **post-deploy validation task**, not a human review: a schema-check
   script (`a_bgt_rsi/scripts/validate_run_log.py`, new) runs immediately after the
   first build and confirms every new entry has a non-null `agent` matching
   `workflow:wf_xxx/<role>`. The script returning **`status: passed`** satisfies
   reconciliation — no manual attestation.
4. **Record the bump in `DECISIONS.md` (both repos)**, linking framework commit
   `2690b5b`, with a status line: _"Rule 6 reconciled — verified via automated
   schema-validation task (`validate_run_log.py`)."_

## Files likely to touch (a_bgt_rsi)
- the inviolate-rules doc (rule 6) — amend the schema.
- the run.jsonl emit/logging module — require `agent`; emit start+finish per role.
- `a_bgt_rsi/scripts/validate_run_log.py` — **new** (the gate).
- `a_bgt_rsi/DECISIONS.md` — reconciliation entry linking `2690b5b`.
- `agent_system/DECISIONS.md` — consumer-adoption note (optional cross-link).

## Acceptance criteria
1. Every new run.jsonl entry has a non-null `agent` matching `^workflow:wf_[^/]+/.+$`
   (or a concrete actor id for non-workflow steps).
2. Each workflow role produces exactly two rows (`start`, `finish`).
3. `validate_run_log.py` exits `status: passed` against a live/test run.
4. `DECISIONS.md` updated and linked to framework `2690b5b`.

## Context-injection prompt for the next a_bgt_rsi session
> **Context:** Implementing P-008 (run-log attribution).
> **Constraint:** the manual human-gated attestation is replaced by an **Automated-Gate**.
> **Instruction:** update the run.jsonl logging logic to require `agent` (and emit
> start+finish per workflow role as `workflow:wf_xxx/<role>`), **and** create/run
> `scripts/validate_run_log.py` that parses run.jsonl to assert the `agent` field is
> present and correctly formatted. Once that script passes, consider Rule 6 reconciled
> and record it in DECISIONS.md linking framework commit 2690b5b.
