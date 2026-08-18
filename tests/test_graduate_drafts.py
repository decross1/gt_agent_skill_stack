#!/usr/bin/env python3
"""The P-009 draft classifier must have no latent automatic write path."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import graduate_drafts as gd  # noqa: E402


def test_monkeypatched_passing_gate_still_keeps_draft_for_human_without_writes(
    tmp_path, monkeypatch,
):
    ledger = tmp_path / "memory" / "brain" / "proposals.jsonl"
    ledger.parent.mkdir(parents=True)
    draft = {
        "timestamp": "2026-08-18T00:00:00Z", "proposal_id": "P-999",
        "status": "draft", "target_type": "brain-page", "target": "daily-view",
        "title": "A local display improvement", "change": "x", "reasoning": "y",
    }
    ledger.write_text(json.dumps(draft) + "\n")
    before = ledger.read_bytes()
    monkeypatch.setattr(gd, "PROPOSALS", ledger)
    monkeypatch.setattr(gd, "blast_radius", lambda _first: "low")
    monkeypatch.setattr(gd, "adversarial_gate", lambda _first: (True, "test pass"))

    actions = gd.graduate(apply=True)

    assert actions == [{
        "proposal_id": "P-999", "blast_radius": "low",
        "title": "A local display improvement", "decision": "kept for human",
        "why": ("adversarial gate passed, but automatic graduation is closed: "
                "no supported attributable automated verdict writer"),
    }]
    assert ledger.read_bytes() == before
    assert not (tmp_path / "handoffs").exists()
    assert not hasattr(gd, "promote_draft")
