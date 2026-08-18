"""Cross-process correctness tests for the proposal-ledger writers.

These tests use only temporary ledgers.  They exercise advisory-lock behavior,
not multi-file transactions or caller authentication.
"""
from __future__ import annotations

import fcntl
import json
import multiprocessing as mp
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import brain_ledger as bl  # noqa: E402
import draft_proposals as dp  # noqa: E402


OPEN_ROW = {
    "timestamp": "2026-08-18T00:00:00Z",
    "proposal_id": "P-901",
    "agent_id": "test",
    "title": "Open proposal",
    "target_type": "skill",
    "target": "validate",
    "change": "x",
    "reasoning": "y",
    "status": "open",
}
SIGNAL = {
    "timestamp": "2026-08-18T00:00:00Z", "signal_id": "DS-1",
    "source": "scan", "detector": "runlog_failure", "skill": "validate",
    "status_observed": "failed", "ref": "framework.run.jsonl:L42",
    "severity": "high", "evidence": "test signal", "scope": "framework",
}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(
        json.dumps(row, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"
        for row in rows
    ))


def _apply_worker(proposals_s: str, feedback_s: str, drift_s: str, result) -> None:
    """Top-level so multiprocessing can run it without serializing modules."""
    import draft_proposals as worker_dp

    worker_dp.PROPOSALS = Path(proposals_s)
    worker_dp.FEEDBACK = Path(feedback_s)
    worker_dp.DRIFT_SIGNALS = Path(drift_s)
    worker_dp.framework_skills = lambda: {"validate"}
    try:
        drafts, _skipped = worker_dp.apply_drafts()
        result.put(("ok", [row["proposal_id"] for row in drafts]))
    except Exception as exc:  # pragma: no cover - assertion reports worker detail
        result.put(("error", repr(exc)))


def _fake_cli(tmp_path: Path) -> tuple[Path, Path]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(REPO / "scripts" / "review_proposal_cli.py", scripts / "review_proposal_cli.py")
    shutil.copy(REPO / "scripts" / "brain_ledger.py", scripts / "brain_ledger.py")
    ledger = tmp_path / "memory" / "brain" / "proposals.jsonl"
    return scripts / "review_proposal_cli.py", ledger


def _run_cli(cli: Path, *args: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(cli), *args], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )


def test_concurrent_draft_apply_allocates_once_and_is_idempotent(tmp_path, monkeypatch):
    """Two simultaneous bubble runs get one proposal, never duplicate IDs."""
    proposals = tmp_path / "memory" / "brain" / "proposals.jsonl"
    feedback = tmp_path / "memory" / "feedback.jsonl"
    drift = tmp_path / "memory" / "brain" / "drift_signals.jsonl"
    _write_jsonl(proposals, [])
    _write_jsonl(feedback, [])
    _write_jsonl(drift, [SIGNAL])
    ctx = mp.get_context("fork")
    result = ctx.Queue()
    workers = [ctx.Process(target=_apply_worker,
                           args=(str(proposals), str(feedback), str(drift), result))
               for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
        assert worker.exitcode == 0
    outcomes = [result.get(timeout=2) for _ in workers]
    assert all(status == "ok" for status, _ids in outcomes), outcomes
    rows = bl.read_proposals(proposals)
    filings = [row for row in rows if "title" in row]
    assert len(filings) == 1
    assert filings[0]["proposal_id"] == "P-001"
    # A later sequential run is a write-free idempotent no-op.
    monkeypatch.setattr(dp, "PROPOSALS", proposals)
    monkeypatch.setattr(dp, "FEEDBACK", feedback)
    monkeypatch.setattr(dp, "DRIFT_SIGNALS", drift)
    monkeypatch.setattr(dp, "framework_skills", lambda: {"validate"})
    before = proposals.read_bytes()
    drafts, _skipped = dp.apply_drafts()
    assert drafts == []
    assert proposals.read_bytes() == before


def test_concurrent_verdicts_leave_one_terminal_verdict(tmp_path):
    cli, ledger = _fake_cli(tmp_path)
    _write_jsonl(ledger, [OPEN_ROW])
    commands = [
        ("--proposal-id", "P-901", "--verdict", verdict, "--note", "race", "--actor", "derrick")
        for verdict in ("accept", "reject")
    ]
    procs = [_run_cli(cli, *command) for command in commands]
    results = [proc.communicate(timeout=10) for proc in procs]
    codes = [proc.returncode for proc in procs]
    assert sorted(codes) == [0, 4], results
    rows = bl.read_proposals(ledger)
    terminal = [row for row in rows if row.get("verdict") in bl.TERMINAL_VERDICTS]
    assert len(terminal) == 1


def test_malformed_ledger_refuses_verdict_without_byte_change(tmp_path):
    cli, ledger = _fake_cli(tmp_path)
    malformed = json.dumps(OPEN_ROW).encode() + b"\n{not json}\n"
    ledger.parent.mkdir(parents=True)
    ledger.write_bytes(malformed)
    proc = subprocess.run(
        [sys.executable, str(cli), "--proposal-id", "P-901", "--verdict", "accept",
         "--note", "x", "--actor", "derrick"], capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 7
    assert ledger.read_bytes() == malformed


def test_lock_timeout_refuses_verdict_without_byte_change(tmp_path):
    cli, ledger = _fake_cli(tmp_path)
    _write_jsonl(ledger, [OPEN_ROW])
    before = ledger.read_bytes()
    lock_path = ledger.with_name(ledger.name + ".lock")
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        proc = subprocess.run(
            [sys.executable, str(cli), "--proposal-id", "P-901", "--verdict", "accept",
             "--note", "x", "--actor", "derrick"], capture_output=True, text=True, timeout=10,
        )
    assert proc.returncode == 6
    assert ledger.read_bytes() == before


def test_accepted_then_evidence_stays_terminal_and_later_review_is_refused(tmp_path):
    cli, ledger = _fake_cli(tmp_path)
    _write_jsonl(ledger, [
        OPEN_ROW,
        {"timestamp": "2026-08-18T00:01:00Z", "proposal_id": "P-901",
         "verdict": "accepted", "status": "closed"},
        {"timestamp": "2026-08-18T00:02:00Z", "proposal_id": "P-901",
         "status": "verified", "verification_ref": "tests:L42"},
    ])
    rows = bl.read_proposals(ledger)
    assert bl.lifecycle_state(rows, "P-901") == "accepted"
    before = ledger.read_bytes()
    proc = subprocess.run(
        [sys.executable, str(cli), "--proposal-id", "P-901",
         "--verdict", "needs_revision", "--note", "try reopening",
         "--actor", "derrick"], capture_output=True, text=True, timeout=10,
    )
    assert proc.returncode == 4
    assert ledger.read_bytes() == before


def test_duplicate_filing_is_fail_closed_without_append(tmp_path):
    ledger = tmp_path / "proposals.jsonl"
    duplicate = [OPEN_ROW, {**OPEN_ROW, "title": "second filing"}]
    _write_jsonl(ledger, duplicate)
    before = ledger.read_bytes()
    with pytest.raises(bl.ProposalLedgerError, match="duplicate filing"):
        with bl.ProposalLedgerLock(ledger):
            pass
    assert ledger.read_bytes() == before


def test_contradictory_terminal_history_is_fail_closed_without_append(tmp_path):
    ledger = tmp_path / "proposals.jsonl"
    _write_jsonl(ledger, [
        OPEN_ROW,
        {"timestamp": "2026-08-18T00:01:00Z", "proposal_id": "P-901",
         "verdict": "accepted", "status": "closed"},
        {"timestamp": "2026-08-18T00:02:00Z", "proposal_id": "P-901",
         "status": "enacted", "commit": "abc123"},
        {"timestamp": "2026-08-18T00:03:00Z", "proposal_id": "P-901",
         "verdict": "rejected", "status": "closed"},
    ])
    before = ledger.read_bytes()
    with pytest.raises(bl.ProposalLedgerError, match="contradictory terminal verdicts"):
        with bl.ProposalLedgerLock(ledger):
            pass
    assert ledger.read_bytes() == before
