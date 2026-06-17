#!/usr/bin/env python3
"""Tests for scripts/scan_drift.py — the deterministic drift detector.

These exercise build_signals() as a pure file->file pass (no LLM, no network):
  - a framework run-log row with a non-enum status -> runlog_schema signal on the
    [[run-log]] skill
  - a framework run-log row with skill_used on a real framework skill AND a
    failure-ish status -> runlog_failure signal on that skill
  - idempotency: feeding the new signals back in yields 0 new on a re-run
  - firewall/safety: the REAL memory/brain/drift_signals.jsonl is never touched

scan_drift pins its inputs/outputs as module-level constants. It imports FW_RUN /
resolve_consumer from draft_proposals into its own namespace and defines
DRIFT_SIGNALS itself, so we monkeypatch scan_drift.FW_RUN, scan_drift.DRIFT_SIGNALS
and scan_drift.resolve_consumer at tmp values. framework_skills() reads
draft_proposals.SKILLS_DIR, so we repoint that at a tmp skills tree holding the
two skills under test — keeping the run hermetic and off the real ledgers.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import scan_drift as sd  # noqa: E402
import draft_proposals as dp  # noqa: E402

REAL_DRIFT_SIGNALS = REPO / "memory" / "brain" / "drift_signals.jsonl"


def _write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


@pytest.fixture
def drift(tmp_path, monkeypatch):
    """A self-contained tmp drift setup: a framework run log, an (empty) signals
    ledger, a tmp skills tree with run-log + validate, and resolve_consumer -> None
    so only the framework run log is scanned. Yields a namespace with the paths and
    helpers to (re)write the run log and read the signals ledger back."""
    run_log = tmp_path / "framework.run.jsonl"
    signals = tmp_path / "drift_signals.jsonl"
    signals.write_text("")

    skills_dir = tmp_path / ".agents" / "skills"
    for name in ("run-log", "validate"):
        (skills_dir / name).mkdir(parents=True)
        (skills_dir / name / "SKILL.md").write_text(
            f"---\nlayer: A\n---\n# {name}\n")

    monkeypatch.setattr(sd, "FW_RUN", run_log)
    monkeypatch.setattr(sd, "DRIFT_SIGNALS", signals)
    monkeypatch.setattr(sd, "resolve_consumer", lambda: None)
    # framework_skills() (reused from draft_proposals) reads SKILLS_DIR.
    monkeypatch.setattr(dp, "SKILLS_DIR", skills_dir)

    class Drift:
        def __init__(self):
            self.run_log = run_log
            self.signals = signals

        def write_run(self, *rows):
            _write_jsonl(run_log, rows)

        def signal_rows(self):
            return [json.loads(l) for l in signals.read_text().splitlines()
                    if l.strip()]

    return Drift()


# A row outside the FR-003 status enum (-> runlog_schema, skill="run-log").
SCHEMA_ROW = {
    "timestamp": "2026-06-01T00:00:00Z", "task_id": "t-schema",
    "status": "recovered",
}
# A framework-skill failure row (-> runlog_failure, skill="validate").
FAILURE_ROW = {
    "timestamp": "2026-06-01T00:01:00Z", "task_id": "t-fail",
    "skill_used": "validate", "status": "failed",
}


# ---------------------------------------------------------------------------
# build_signals — the two deterministic detectors fire on a tmp run log
# ---------------------------------------------------------------------------

def test_build_signals_emits_schema_and_failure_signals(drift):
    drift.write_run(SCHEMA_ROW, FAILURE_ROW)
    new, skipped = sd.build_signals()

    assert skipped == []
    by_detector = {s["detector"]: s for s in new}
    assert set(by_detector) == {"runlog_schema", "runlog_failure"}

    schema = by_detector["runlog_schema"]
    assert schema["skill"] == "run-log"
    assert schema["status_observed"] == "recovered"
    assert schema["severity"] == "low"          # schema flags are low severity
    assert schema["source"] == "scan"
    assert schema["scope"] == "framework"
    assert schema["ref"].startswith("framework.run.jsonl:L")

    failure = by_detector["runlog_failure"]
    assert failure["skill"] == "validate"
    assert failure["status_observed"] == "failed"
    assert failure["severity"] == "low"         # 'failed' is not aborted/escalated
    assert failure["source"] == "scan"
    assert failure["scope"] == "framework"

    # ids are sequential, zero-padded DS-NNNN, unique.
    ids = sorted(s["signal_id"] for s in new)
    assert ids == ["DS-0001", "DS-0002"]


def test_build_signals_high_severity_on_aborted_failure(drift):
    """A failure-ish status in {aborted, escalated} escalates to high severity."""
    drift.write_run({"timestamp": "2026-06-01T00:02:00Z", "task_id": "t-abort",
                     "skill_used": "validate", "status": "aborted"})
    new, _ = sd.build_signals()
    assert len(new) == 1
    assert new[0]["detector"] == "runlog_failure"
    assert new[0]["severity"] == "high"


# ---------------------------------------------------------------------------
# idempotency — appending the emitted signals, then re-running, yields 0 new
# ---------------------------------------------------------------------------

def test_build_signals_is_idempotent_after_append(drift):
    drift.write_run(SCHEMA_ROW, FAILURE_ROW)
    first, _ = sd.build_signals()
    assert len(first) == 2

    # Simulate --apply: append exactly what was minted to the tmp ledger.
    sd.append_signals(first)
    assert len(drift.signal_rows()) == 2

    # A second pass over the unchanged run log mints nothing new and explains the
    # no-op via the skipped list (keyed on (detector, ref)).
    second, skipped = sd.build_signals()
    assert second == []
    assert len(skipped) == 2
    assert all(s["reason"] == "already detected" for s in skipped)
    # Nothing else got appended.
    assert len(drift.signal_rows()) == 2


# ---------------------------------------------------------------------------
# firewall / safety — the real ledger is never written
# ---------------------------------------------------------------------------

def test_real_drift_signals_ledger_untouched(drift):
    before = (REAL_DRIFT_SIGNALS.read_text()
              if REAL_DRIFT_SIGNALS.exists() else None)
    drift.write_run(SCHEMA_ROW, FAILURE_ROW)
    new, _ = sd.build_signals()
    sd.append_signals(new)  # writes to the monkeypatched tmp ledger only

    after = (REAL_DRIFT_SIGNALS.read_text()
             if REAL_DRIFT_SIGNALS.exists() else None)
    assert after == before  # real ledger byte-identical (incl. still-absent)
    # And the writes landed in the tmp ledger.
    assert len(drift.signal_rows()) == 2
