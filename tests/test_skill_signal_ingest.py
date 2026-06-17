#!/usr/bin/env python3
"""Tests for scripts/ingest_apparatus.py — the runtime skill-signal lane.

Two surfaces under test (both pure, no LLM, no consumer writes):
  - project_skill_signal(src, lineno) — narrative projection of an agent's
    self-reported skill signal (agent_id + task_id).
  - project_skill_signal_drift(src, lineno, task_id) + _SIGNAL_CLASS_MAP — the
    source="runtime" drift_signals row, where signal_class is mapped onto the
    SHARED drift status vocabulary (misuse → diverged).

We also drive the real build path (derive_drift_rows) over the on-disk fixture
tests/fixtures/skill_signals.jsonl, allocating DS-NNNN from a tmp empty
drift ledger so no real ledger is read or written.
"""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import ingest_apparatus as ia  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "skill_signals.jsonl"

# The sample skill-signal dict from the task spec (a `misuse` on `fallback`).
SAMPLE = {
    "signal_class": "misuse", "skill": "fallback", "agent": "nara",
    "evidence": "switched to the fallback decoder before the primary hit its cap",
    "task_id": "t1", "severity": "low",
}


def test_project_skill_signal_narrative():
    narr = ia.project_skill_signal(SAMPLE, lineno=3)
    assert narr["agent_id"] == "nara"
    assert narr["task_id"] == "t1"
    # intent names the class + skill; observed echoes class + severity.
    assert "fallback" in narr["intent"]
    assert "misuse" in narr["intent"]
    assert "signal_class=misuse" in narr["observed"]


def test_project_skill_signal_default_task_id():
    # Missing task_id falls back to a deterministic, lineno-derived id.
    narr = ia.project_skill_signal({"signal_class": "gap", "skill": "validate"}, lineno=7)
    assert narr["task_id"] == "signal_L7"
    assert narr["agent_id"] == "nara"   # default agent when none supplied


def test_signal_class_map_misuse_diverged():
    # The mapping the drift row uses: misuse → diverged, others pass through.
    assert ia._SIGNAL_CLASS_MAP["misuse"] == "diverged"
    assert ia._SIGNAL_CLASS_MAP["diverged"] == "diverged"
    assert ia._SIGNAL_CLASS_MAP["friction"] == "friction"
    assert ia._SIGNAL_CLASS_MAP["gap"] == "gap"


def test_project_skill_signal_drift_maps_misuse_to_diverged():
    row = ia.project_skill_signal_drift(SAMPLE, lineno=3, task_id="t1")
    assert row["source"] == "runtime"
    assert row["detector"] == "runtime_selfreport"
    assert row["skill"] == "fallback"
    assert row["scope"] == "framework"
    assert row["severity"] == "low"
    # misuse → diverged, but the original word is preserved in evidence.
    assert row["status_observed"] == "diverged"
    assert "[misuse]" in row["evidence"]
    # ref carries the source line + the task id.
    assert row["ref"] == "skill_signals.jsonl:L3 task=t1"


def test_project_skill_signal_drift_passthrough_class():
    # A class that maps to itself does not get the [orig] prefix.
    src = {"signal_class": "friction", "skill": "run-log", "severity": "low",
           "evidence": "enum too narrow"}
    row = ia.project_skill_signal_drift(src, lineno=1, task_id="t9")
    assert row["status_observed"] == "friction"
    assert not row["evidence"].startswith("[friction]")


def _projected_pairs_from_fixture(path: Path):
    """Run the module's own per-line projection over the fixture, returning the
    (narrative, source) pairs derive_drift_rows expects (mirrors ingest_one)."""
    pairs = []
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        src = json.loads(raw)
        proj = ia.project(src, lineno, strict=True)
        assert proj is not None, f"line {lineno} should project (skill-signal shape)"
        narrative = {
            "timestamp": src.get("timestamp", ""),
            "task_id": proj["task_id"],
            "agent_id": proj["agent_id"],
            "_source": {"file": path.name, "line": lineno},
        }
        pairs.append((narrative, src))
    return pairs


def test_build_path_over_fixture_emits_runtime_drift_rows(tmp_path):
    # Point the build path at a TEMP empty drift ledger; never the real one.
    drift = tmp_path / "drift_signals.jsonl"
    drift.write_text("")
    start_id = ia.next_drift_signal_id(drift)
    assert start_id == 1   # empty ledger → first id is DS-0001

    pairs = _projected_pairs_from_fixture(FIXTURE)
    assert len(pairs) == 3   # all three sample signals are skill-signal shaped

    rows = ia.derive_drift_rows(pairs, existing_drift_keys=set(),
                                start_signal_id=start_id)
    assert len(rows) == 3
    # Sequential DS ids from the start.
    assert [r["signal_id"] for r in rows] == ["DS-0001", "DS-0002", "DS-0003"]
    # Every row is a runtime self-report, framework-scoped.
    assert all(r["source"] == "runtime" for r in rows)
    assert all(r["scope"] == "framework" for r in rows)
    # The `misuse` fixture line (fallback) maps to diverged; the others pass through.
    by_skill = {r["skill"]: r for r in rows}
    assert by_skill["fallback"]["status_observed"] == "diverged"
    assert by_skill["run-log"]["status_observed"] == "friction"
    assert by_skill["validate"]["status_observed"] == "gap"


def test_build_path_idempotent_on_existing_keys(tmp_path):
    pairs = _projected_pairs_from_fixture(FIXTURE)
    # Pre-seed the dedup set with every (file, line) → no new rows.
    existing = {(p[0]["_source"]["file"], p[0]["_source"]["line"]) for p in pairs}
    rows = ia.derive_drift_rows(pairs, existing_drift_keys=set(existing),
                                start_signal_id=1)
    assert rows == []
