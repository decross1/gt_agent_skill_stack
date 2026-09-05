"""Semantic port guardrails over the published actor and ledger contracts."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_summary as ps
import project_pages as pp
import proposal_health as ph
import brain_snapshot as snapshot
from brain_ledger import ProposalLedgerError


def test_backdated_evidence_keeps_structured_actor_and_governing_verdict(monkeypatch):
    commit = "a" * 40
    path = ".agents/skills/validate/SKILL.md"
    actor = {"id": "oracle", "type": "agent", "authentication": "ui-asserted",
             "cryptographically_authenticated": False}
    rows = [
        {"proposal_id": "P-901", "title": "Synthetic port", "target_type": "skill",
         "target": "validate", "status": "open", "timestamp": "2026-08-01T00:00:00Z"},
        {"proposal_id": "P-901", "verdict": "accepted", "status": "closed",
         "timestamp": "2026-08-03T00:00:00Z", "actor": actor},
        {"proposal_id": "P-901", "timestamp": "2026-08-02T00:00:00Z",
         "enactment": {"commit": commit, "paths": [path]}},
        {"proposal_id": "P-901", "timestamp": "2026-08-02T01:00:00Z",
         "verification": {"commit": commit, "command": "synthetic check", "result": "pass", "output_sha256": "b" * 64}},
    ]
    monkeypatch.setattr(ps, "_commit_changed_paths", lambda *_: {path})
    proposals = ps.collapse_proposals(rows)
    chain = ps.build_loop(proposals, [], [], [], "2026-08-04")["chains"][0]
    assert chain["healing"]["enacted"]["state"] == "enacted"
    assert chain["healing"]["verified"]["state"] == "pending"
    assert chain["governing_verdict_actor"]["id"] == "oracle"
    assert chain["lifecycle"][2]["actor"] == "unknown"
    assert chain["lifecycle"][2]["actor_detail"]["source"] == "missing_actor"
    assert chain["lifecycle"][2]["governing_verdict_actor"]["cryptographically_authenticated"] is False
    timeline, _ = ps.build_timeline_and_incidents(proposals, [], [], {}, [], [], [], [], None, "2026-08-01", "2026-08-04")
    evidence = [row for row in timeline if row["kind"] == "proposal_evidence_reported"]
    assert len(evidence) == 2 and all(row["agent"] == "unknown" for row in evidence)
    reviewed = next(row for row in timeline if row["kind"] == "proposal_reviewed")
    assert reviewed["agent"] == "oracle"


@pytest.mark.parametrize("reader", ["pages", "health", "snapshot"])
def test_ported_readers_still_reject_unknown_proposal_rows(tmp_path, monkeypatch, reader):
    path = tmp_path / "proposals.jsonl"
    path.write_text(json.dumps({"unknown": "unsupported"}) + "\n")
    if reader == "pages":
        read = lambda: pp.load_proposals(path)
    elif reader == "health":
        read = lambda: ph.load_proposals(path)
    else:
        monkeypatch.setattr(snapshot, "PROPOSALS", path)
        read = snapshot.days_since_last_human_review
    with pytest.raises((ProposalLedgerError, ValueError)):
        read()


def test_snapshot_error_keeps_physical_line_after_exact_legacy_quarantine(tmp_path, monkeypatch):
    from test_proposal_writer_locking import (
        _legacy_prelock_pair, _bind_synthetic_legacy_hashes, _write_jsonl,
    )
    pair = _legacy_prelock_pair()
    _bind_synthetic_legacy_hashes(monkeypatch, pair)
    rows = [{"proposal_id": "P-901", "title": "Synthetic filing"}, *pair,
            {"proposal_id": "P-901", "status": "closed", "verdict": "rejected",
             "timestamp": "invalid-recorded-time"}]
    path = tmp_path / "proposals.jsonl"
    _write_jsonl(path, rows)
    before = path.read_bytes()
    monkeypatch.setattr(snapshot, "PROPOSALS", path)
    with pytest.raises(ValueError, match=r"proposals.jsonl:4: timestamp"):
        snapshot.days_since_last_proposal_closed()
    assert path.read_bytes() == before
