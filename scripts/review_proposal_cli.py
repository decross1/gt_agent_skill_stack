#!/usr/bin/env python3
"""Blessed CLI for recording a governed verdict on a brain proposal.

The brain UI's Accept / Reject buttons exec THIS via argv (no shell) — an
evolution of the D-046 human-write-back pattern into a closed, attributable
Derrick-or-Oracle steward review. Out-of-enum input exits nonzero and writes
nothing. It is also runnable from a terminal.

It records the governed *verdict* (append-only) — it does NOT enact the change.
Enacting a skill/rule edit is a separate dev-session / handoff step. A Derrick
or Oracle acceptance is an asserted, attributable steward-review transition;
it is not authentication, consensus, or an automated skill mutation. The
caller must explicitly choose one closed actor identity. That identity is
asserted by the UI/CLI caller; it is not cryptographically authenticated.

Exit codes: 0 ok · 2 bad proposal_id · 3 unknown proposal · 4 already decided
· 5 missing note · 6 io error · 7 corrupt ledger.

All exits print a single-line JSON object so the calling UI can parse the
outcome deterministically; nothing is written unless the verdict is recorded.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from brain_ledger import (
    ACCEPTED_BODY_SCHEMA_VERSION,
    DECISION_SCHEMA_VERSION,
    ProposalLedgerError,
    ProposalLedgerLock,
    ProposalLedgerTimeout,
    accepted_body_digest,
    lifecycle_state,
    proposal_is_open,
)

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / "memory" / "brain" / "proposals.jsonl"

# frozen enum: CLI arg -> recorded verdict
VERDICTS = {"accept": "accepted", "reject": "rejected", "needs_revision": "human-review"}
PID_RE = re.compile(r"^P-\d+$")

# Closed, deliberately small attribution vocabulary.  This is an assertion
# supplied by a local UI/terminal user, not an authentication mechanism.
ACTORS = {
    "derrick": {
        "id": "derrick",
        "type": "human",
        "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    },
    "oracle": {
        "id": "oracle",
        "type": "agent",
        "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    },
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Record a governed verdict on a brain proposal.")
    ap.add_argument("--proposal-id", required=True)
    ap.add_argument("--verdict", required=True, choices=sorted(VERDICTS))
    ap.add_argument("--note", default="", help="decision reasoning — required to reject/needs_revision (a rejection without a reason is an opinion); optional for accept")
    ap.add_argument("--actor", required=True, choices=sorted(ACTORS),
                    help="closed asserted identity: derrick or oracle (not cryptographically authenticated)")
    ap.add_argument("--basis", default="original", choices=("original", "amended"),
                    help="which draft the verdict governs: the original proposal or the synthesized amended draft")
    ap.add_argument("--accepted-body", default=None,
                    help="exact final amended proposal body; required only for accept --basis amended")
    a = ap.parse_args()

    if not PID_RE.match(a.proposal_id):
        print(json.dumps({"ok": False, "error": "bad proposal_id (want P-NNN)"}))
        sys.exit(2)
    if a.verdict != "accept" and not a.note.strip():
        print(json.dumps({"ok": False, "error": "note (reason) required to reject/needs_revision"}))
        sys.exit(5)
    if a.accepted_body is not None and (a.verdict != "accept" or a.basis != "amended"):
        print(json.dumps({"ok": False, "error": "accepted body is only valid for accept --basis amended"}))
        sys.exit(2)
    if a.verdict == "accept" and a.basis == "amended":
        if not isinstance(a.accepted_body, str) or not a.accepted_body.strip():
            print(json.dumps({"ok": False, "error": "accepted body required for accept --basis amended"}))
            sys.exit(2)
        try:
            # Validate the exact argv value before taking the ledger lock. The
            # value itself is deliberately not stripped or normalized.
            accepted_body_digest(a.accepted_body)
        except ProposalLedgerError as e:
            print(json.dumps({"ok": False, "error": str(e)}))
            sys.exit(2)

    verdict = VERDICTS[a.verdict]
    try:
        # The complete read → lifecycle decision → durable append is one
        # cross-process critical section.  A concurrent reviewer therefore sees
        # the first terminal verdict and refuses to add a contradictory second.
        with ProposalLedgerLock(PROPOSALS) as ledger:
            if lifecycle_state(ledger.rows, a.proposal_id) is None:
                print(json.dumps({"ok": False, "error": "unknown proposal"}))
                sys.exit(3)
            if not proposal_is_open(ledger.rows, a.proposal_id):
                current = lifecycle_state(ledger.rows, a.proposal_id)
                print(json.dumps({"ok": False, "error": f"already {current}"}))
                sys.exit(4)
            accepted_body = None
            if verdict == "accepted":
                if a.basis == "amended":
                    accepted_body = a.accepted_body
                else:
                    filing = next((row for row in ledger.rows
                                   if row["proposal_id"] == a.proposal_id and "title" in row), None)
                    if filing is None or not isinstance(filing.get("change"), str):
                        raise ProposalLedgerError("original filing has no reconstructible change body")
                    accepted_body = filing["change"]
                digest = accepted_body_digest(accepted_body)
            out = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "proposal_id": a.proposal_id,
                "supersedes_proposal_id": a.proposal_id,
                # `agent_id` remains a scalar compatibility mirror for readers of
                # legacy proposal rows. New readers should use the structured actor.
                "agent_id": a.actor,
                "actor": dict(ACTORS[a.actor]),
                "verdict": verdict,
                "verdict_reasoning": a.note.strip(),
                "basis": a.basis,
                "rule_cited": None,
                "decision_id": None,
                "status": "human-review" if verdict == "human-review" else "closed",
            }
            if verdict == "accepted":
                out.update({
                    "decision_schema_version": DECISION_SCHEMA_VERSION,
                    "accepted_body_schema": ACCEPTED_BODY_SCHEMA_VERSION,
                    "accepted_body": accepted_body,
                    "accepted_body_sha256": digest,
                })
            ledger.append([out])
    except ProposalLedgerTimeout as e:
        print(json.dumps({"ok": False, "error": f"io: {e}"}))
        sys.exit(6)
    except ProposalLedgerError as e:
        # Fail closed: do not record a verdict against an unreadable ledger.
        print(json.dumps({"ok": False, "error": f"corrupt ledger: {e}"}))
        sys.exit(7)
    print(json.dumps({"ok": True, "recorded": verdict, "proposal_id": a.proposal_id,
                      "actor": ACTORS[a.actor]}))


if __name__ == "__main__":
    main()
