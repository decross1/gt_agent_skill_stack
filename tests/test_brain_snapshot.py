"""Snapshot metrics require recorded observations, not inferred session boundaries."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import brain_snapshot as snapshot


def ledger(tmp_path, monkeypatch, attr, rows):
    path = tmp_path / (attr + ".jsonl")
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(snapshot, attr, path)
    return path


def test_rejected_proposal_is_a_recorded_closure(tmp_path, monkeypatch):
    timestamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    ledger(tmp_path, monkeypatch, "PROPOSALS", [
        {"proposal_id": "P-900", "title": "Synthetic closure", "timestamp": timestamp, "status": "closed", "verdict": "rejected"},
    ])
    assert snapshot.days_since_last_human_review() == pytest.approx(2, abs=0.001)


def test_historical_task_prefixes_do_not_measure_resume_time(tmp_path, monkeypatch):
    ledger(tmp_path, monkeypatch, "FW_RUN", [
        {"task_id": "s24_resume", "timestamp": "2026-08-01T00:00:00Z"},
        {"task_id": "s24_build", "timestamp": "2026-08-01T00:00:10Z"},
    ])
    assert snapshot.median_time_to_resume(5) is None


def receipt(sid, kind, timestamp):
    return {"session_id": sid, "kind": kind, "timestamp": timestamp,
            "task_id": sid + "_" + kind}


def test_explicit_receipts_use_latest_sessions_by_start_time(tmp_path, monkeypatch):
    ledger(tmp_path, monkeypatch, "FW_RUN", [
        receipt("new", "session_start", "2026-08-02T00:00:00Z"),
        receipt("new", "task_start", "2026-08-02T00:00:05Z"),
        receipt("old", "session_start", "2026-08-01T00:00:00Z"),
        receipt("old", "task_start", "2026-08-01T00:00:10Z"),
    ])
    assert snapshot.median_time_to_resume(1) == 5
    assert snapshot.median_time_to_resume(2) == 7.5


@pytest.mark.parametrize("k", [0, -1])
def test_nonpositive_window_is_invalid(tmp_path, monkeypatch, k):
    ledger(tmp_path, monkeypatch, "FW_RUN", [])
    with pytest.raises(ValueError, match="positive"):
        snapshot.median_time_to_resume(k)


@pytest.mark.parametrize("extra", [
    receipt("one", "task_start", "2026-07-31T23:59:59Z"),
    receipt("one", "session_start", "2026-08-01T00:00:01Z"),
])
def test_negative_interval_or_reused_session_id_is_not_measured(tmp_path, monkeypatch, extra):
    ledger(tmp_path, monkeypatch, "FW_RUN", [
        receipt("one", "session_start", "2026-08-01T00:00:00Z"), extra,
        receipt("one", "task_start", "2026-08-01T00:00:10Z"),
    ])
    assert snapshot.median_time_to_resume(5) is None


def test_task_receipt_before_its_session_start_makes_timing_ambiguous(tmp_path, monkeypatch):
    ledger(tmp_path, monkeypatch, "FW_RUN", [
        receipt("one", "task_start", "2026-07-31T23:59:59Z"),
        receipt("one", "session_start", "2026-08-01T00:00:00Z"),
        receipt("one", "task_start", "2026-08-01T00:00:05Z"),
    ])
    assert snapshot.median_time_to_resume(5) is None


@pytest.mark.parametrize("value", ["{broken", "[]", "null"])
def test_invalid_ledger_row_reports_path_and_line(tmp_path, monkeypatch, value):
    path = ledger(tmp_path, monkeypatch, "PROPOSALS", [])
    path.write_text(json.dumps({"proposal_id": "P-900", "title": "Synthetic filing"}) + "\n" + value + "\n")
    # The retained governed parser gives physical positions for valid JSON
    # shape errors; JSON syntax errors carry its original parser diagnostic.
    diagnostic = r"PROPOSALS.jsonl:malformed JSONL" if value == "{broken" else r"PROPOSALS.jsonl:2"
    with pytest.raises(ValueError, match=diagnostic):
        snapshot.days_since_last_human_review()


@pytest.mark.parametrize("timestamp", ["not-a-date", "2026-08-01T00:00:00", 42, "2099-01-01T00:00:00Z"])
def test_unusable_closure_timestamp_is_not_a_metric(tmp_path, monkeypatch, timestamp):
    ledger(tmp_path, monkeypatch, "PROPOSALS", [
        {"proposal_id": "P-900", "title": "Synthetic closure", "status": "closed", "verdict": "accepted", "timestamp": timestamp},
    ])
    with pytest.raises(ValueError, match="timestamp"):
        snapshot.days_since_last_human_review()


def test_cli_discloses_missing_receipts_and_does_not_claim_improvement(tmp_path, monkeypatch, capsys):
    ledger(tmp_path, monkeypatch, "PROPOSALS", [])
    ledger(tmp_path, monkeypatch, "FW_RUN", [])
    monkeypatch.setattr(sys, "argv", ["brain_snapshot.py"])
    assert snapshot.main() == 0
    output = capsys.readouterr().out
    assert "explicit session_start/task_start receipts" in output
    assert "Compounds if" not in output


def test_cli_returns_error_without_printing_partial_metrics(tmp_path, monkeypatch, capsys):
    path = ledger(tmp_path, monkeypatch, "PROPOSALS", [])
    path.write_text("not json\n")
    monkeypatch.setattr(sys, "argv", ["brain_snapshot.py"])
    assert snapshot.main() == 2
    output = capsys.readouterr()
    assert not output.out
    assert "PROPOSALS.jsonl:malformed JSONL" in output.err
