---
slug: "dec-ap-d-046-human-write-back-contract-blessed-ui"
type: "decision"
date: "2026-06-10"
source: "a_bgt_rsi/DECISIONS.md"
---

# D-046 — Human write-back contract blessed: UI POSTs exec blessed CLIs; defer-to-dev-session queue + startup triage step

_apparatus decision_

**Date locked.** 2026-06-10 (screenshot-review session; ratified by the human at
planning time).

**Decision.** The UI's deferred "B4 write-back" ships against a blessed CLI contract
(`docs/human_writeback_contract.md`): `ui/backend` POST endpoints exec the CLIs as
**argv arrays, no shell** — `gate_cli` for gate verdicts (enum frozen
valid|invalid|needs_revision), NEW `finding_session --set-status` one-shot for quick
finding dispositions (validated|rejected|in_review; validated/rejected route
`gate_cli.append_feedback` against the finding's source iteration exactly as
`end_session` does), NEW `todo_cli ack` for bubble acks (`memory/coordinator_acks.jsonl`,
the join key `ui/backend/human_todo.py` already reads), and NEW `todo_cli defer` —
a **defer-to-dev-session** disposition appending
`{ref_id, kind, note, status:"open", attested_by, deferred_at}` to
`memory/dev_session_queue.jsonl` (append-only; `close` appends a closing row; readers
fold by ref_id, last status wins). Writes from the UI stamp `human:ui`. CLI validation
is the gate: out-of-enum exits nonzero, writes nothing, stderr surfaced verbatim.
CLAUDE.md "How to start a primary session" gains one step: run
`todo_cli list-deferred` and triage open deferrals into the session plan.
`stale_active_run` / `state_gate` direct resolution stays a primary-session human
action — defer-only from the UI.

**Alternatives rejected.** (a) UI writes `memory/*` files directly — breaks the
single-writer discipline every ledger relies on; (b) a separate primary-owned API
service — a second server to run/version for no added safety over exec-ing the same
CLIs; (c) reusing `run_state/attestations.jsonl` — that is retired track-era machinery
(soft-gate SLA log), and overloading it would resurrect retired semantics.

**Reversibility.** Endpoints are additive; the queue file is append-only; removing the
blessing reverts the UI to copy-paste rendering with no data migration.
