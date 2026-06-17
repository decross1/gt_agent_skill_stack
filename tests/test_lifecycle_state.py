#!/usr/bin/env python3
"""Tests for project_summary.lifecycle_state — the proposal LANE authority.

lifecycle_state maps a collapsed-proposal dict ({first, latest, lifecycle[]}) to
one of draft | open | human-review | closed. It is the authority that keeps a
bubbled DRAFT (status=='draft', no verdict) out of the open review queue, while
an append-only promotion row (status 'open', or any verdict) flips it out of the
draft lane WITHOUT rewriting the original draft row.

These are pure-function tests: we hand-build collapsed dicts (no ledger, no
monkeypatch needed — lifecycle_state reads p['latest']) and assert each lane.
The dicts carry first/latest/lifecycle to mirror collapse_proposals' shape.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import project_summary as ps  # noqa: E402


def _collapsed(*rows):
    """Build a {first, latest, lifecycle} collapsed-proposal dict from time-ordered
    lifecycle rows, exactly as collapse_proposals would."""
    rows = list(rows)
    return {"first": rows[0], "latest": rows[-1], "lifecycle": rows}


DRAFT_ROW = {
    "timestamp": "2026-06-01T00:00:00Z", "proposal_id": "P-500",
    "title": "Bubbled candidate", "target_type": "skill", "target": "validate",
    "change": "x", "reasoning": "y", "status": "draft",
}
OPEN_ROW = {
    "timestamp": "2026-06-01T00:00:00Z", "proposal_id": "P-501",
    "title": "A filed proposal", "target_type": "skill", "target": "validate",
    "change": "x", "reasoning": "y", "status": "open",
}


def test_draft_is_draft_never_open():
    """status=='draft' with no verdict -> 'draft' (and explicitly NOT 'open', the
    leak lifecycle_state exists to prevent)."""
    state = ps.lifecycle_state(_collapsed(DRAFT_ROW))
    assert state == "draft"
    assert state != "open"


def test_open_filing_is_open():
    """A filing whose latest row is status 'open' with no verdict -> 'open'."""
    assert ps.lifecycle_state(_collapsed(OPEN_ROW)) == "open"


def test_draft_promoted_to_open_is_open():
    """A draft followed by an append-only promotion row (status 'open') -> 'open':
    keying off the LATEST row flips the lane without rewriting the draft."""
    promotion = dict(DRAFT_ROW, timestamp="2026-06-02T00:00:00Z", status="open")
    assert ps.lifecycle_state(_collapsed(DRAFT_ROW, promotion)) == "open"


def test_accepted_verdict_is_closed():
    """A verdict 'accepted' on the latest row -> 'closed' (decided lane)."""
    verdict = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-501",
               "agent_id": "human:ui", "verdict": "accepted", "status": "closed"}
    assert ps.lifecycle_state(_collapsed(OPEN_ROW, verdict)) == "closed"


def test_rejected_verdict_is_closed():
    """A 'rejected' verdict is also a closed (decided) proposal."""
    verdict = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-501",
               "agent_id": "human:ui", "verdict": "rejected", "status": "closed"}
    assert ps.lifecycle_state(_collapsed(OPEN_ROW, verdict)) == "closed"


def test_human_review_verdict_is_human_review():
    """verdict 'human-review' is its own lane, distinct from closed."""
    verdict = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-501",
               "agent_id": "review-proposal", "verdict": "human-review",
               "status": "human-review"}
    assert ps.lifecycle_state(_collapsed(OPEN_ROW, verdict)) == "human-review"
