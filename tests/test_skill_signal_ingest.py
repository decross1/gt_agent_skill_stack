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
    # The receiver accepts exactly three input classes; misuse maps on output.
    assert ia._SIGNAL_CLASS_MAP["misuse"] == "diverged"
    assert ia._SIGNAL_CLASS_MAP["friction"] == "friction"
    assert ia._SIGNAL_CLASS_MAP["gap"] == "gap"
    assert set(ia._SIGNAL_CLASS_MAP) == {"friction", "misuse", "gap"}


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


@pytest.mark.parametrize("signal_class", ["diverged", "typo-class", "", [], {}, None, 3])
def test_invalid_signal_class_never_projects_as_runtime_drift(signal_class):
    src = {"signal_class": signal_class, "skill": "validate"}
    assert ia.project(src, lineno=4, strict=True) is None
    with pytest.raises(ValueError, match="^invalid_signal_class$"):
        ia.project_skill_signal_drift(src, lineno=4, task_id="signal_L4")


@pytest.mark.parametrize("skill", ["", "   ", [], {}, None, 3])
def test_invalid_skill_never_projects_as_runtime_drift(skill):
    src = {"signal_class": "gap", "skill": skill}
    assert ia.project(src, lineno=9, strict=True) is None
    with pytest.raises(ValueError, match="^invalid_skill$"):
        ia.project_skill_signal_drift(src, lineno=9, task_id="signal_L9")


def test_unknown_skill_is_narrative_only_with_exact_reason():
    src = {"signal_class": "gap", "skill": "not-a-framework-skill"}
    proj = ia.project(src, lineno=12, strict=True)
    assert proj is not None
    assert proj["task_id"] == "signal_L12"
    pair = ({"timestamp": "", "task_id": proj["task_id"], "agent_id": proj["agent_id"],
             "_source": {"file": "skill_signals.jsonl", "line": 12}}, src)
    report = {}
    assert ia.derive_drift_rows([pair], set(), 1, signal_report=report) == []
    assert report["examples"] == [{
        "disposition": "narrative_only",
        "reason": "unknown_skill",
        "ref": "skill_signals.jsonl:L12",
    }]
    with pytest.raises(ValueError, match="^unknown_skill$"):
        ia.project_skill_signal_drift(src, lineno=12, task_id="signal_L12")


@pytest.mark.parametrize("signal_class,reason", [
    ("gap", "overlapping_non_signal"),
    ("typo-class", "overlapping_non_signal"),
])
def test_overlapping_runlog_payload_stays_non_signal(signal_class, reason):
    src = {
        "signal_class": signal_class,
        "skill": "validate",
        "task_id": "ordinary-run",
        "status": "passed",
        "observable_actual": "ordinary event",
    }
    proj = ia.project(src, lineno=13, strict=True)
    assert proj is not None
    assert proj["task_id"] == "ordinary-run"
    assert "status=passed" in proj["observed"]
    pair = ({"timestamp": "", "task_id": proj["task_id"], "agent_id": proj["agent_id"],
             "_source": {"file": "skill_signals.jsonl", "line": 13}}, src)
    report = {}
    assert ia.derive_drift_rows([pair], set(), 1, signal_report=report) == []
    assert report["examples"][0]["reason"] == reason


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))


def _run_cli(monkeypatch, logs: Path, state: Path, outputs: tuple[Path, Path, Path],
             *, dry_run: bool) -> int:
    argv = [
        "ingest_apparatus.py", "--logs-dir", str(logs), "--state-dir", str(state),
        "--narratives", str(outputs[0]), "--edges", str(outputs[1]),
        "--drift", str(outputs[2]),
    ]
    if dry_run:
        argv.append("--dry-run")
    monkeypatch.setattr(sys, "argv", argv)
    return ia.main()


@pytest.mark.parametrize("status", ["failed", "refused", "escalated"])
@pytest.mark.parametrize("signal_hint", [False, True])
def test_ordinary_runlog_is_not_reported_as_a_rejected_selfreport(
    tmp_path, monkeypatch, capsys, status, signal_hint
):
    logs = tmp_path / "consumer" / "logs"
    logs.mkdir(parents=True)
    state = tmp_path / "consumer" / "run_state"
    ordinary = {"task_id": "ordinary", "status": status,
                "observable_actual": "The skill correctly recorded this outcome."}
    if signal_hint:
        ordinary.update(signal_class="typo-class", skill="validate")
    _write_jsonl(state / "skill_signals.jsonl", [ordinary])
    outputs = tuple(tmp_path / "outputs" / name for name in
                    ("narratives.jsonl", "edges.jsonl", "drift.jsonl"))
    assert _run_cli(monkeypatch, logs, state, outputs, dry_run=False) == 0
    narrative = json.loads(outputs[0].read_text())
    assert narrative["task_id"] == "ordinary"
    assert f"status={status}" in narrative["observed"]
    assert outputs[2].read_bytes() == b""
    stdout = capsys.readouterr().out
    assert "rejected" not in stdout
    if signal_hint:
        assert "non_signal reason=overlapping_non_signal ref=skill_signals.jsonl:L1" in stdout
    else:
        assert "signal admission:" not in stdout


def test_stage_hint_is_non_signal_and_dedicated_non_object_is_rejected(
    tmp_path, monkeypatch, capsys
):
    logs = tmp_path / "consumer" / "logs"
    logs.mkdir(parents=True)
    state = tmp_path / "consumer" / "run_state"
    _write_jsonl(state / "skill_signals.jsonl", [
        {"stage": "inspect", "detail": "ordinary stage", "task_id": "stage",
         "signal_class": "typo-class", "skill": "validate"},
        None,
    ])
    outputs = tuple(tmp_path / "outputs" / name for name in
                    ("narratives.jsonl", "edges.jsonl", "drift.jsonl"))
    assert _run_cli(monkeypatch, logs, state, outputs, dry_run=False) == 0
    assert len(outputs[0].read_text().splitlines()) == 1
    assert outputs[2].read_bytes() == b""
    stdout = capsys.readouterr().out
    assert "non_signal reason=overlapping_non_signal ref=skill_signals.jsonl:L1" in stdout
    assert "rejected reason=invalid_signal_object ref=skill_signals.jsonl:L2" in stdout
    assert "invalid_signal_class" not in stdout


def test_full_cli_dry_run_absent_outputs_and_parents_remain_absent(
    tmp_path, monkeypatch, capsys
):
    consumer = tmp_path / "consumer"
    logs = consumer / "logs"
    logs.mkdir(parents=True)
    state = consumer / "run_state"
    _write_jsonl(state / "skill_signals.jsonl", [
        {"signal_class": "gap", "skill": "validate"},
        {"signal_class": "typo-class", "skill": "validate"},
        {"signal_class": "gap", "skill": []},
        {"signal_class": "gap", "skill": "not-a-framework-skill"},
    ])
    # The only sibling discovery root is private and declared under tmp_path.
    _write_jsonl(consumer / ".claude" / "worktrees" / "private" / "logs" / "event.jsonl", [
        {"task_id": "sibling", "status": "passed", "observable_actual": "private"},
    ])
    output_parent = tmp_path / "absent" / "nested"
    outputs = tuple(output_parent / name for name in ("narratives.jsonl", "edges.jsonl", "drift.jsonl"))

    assert _run_cli(monkeypatch, logs, state, outputs, dry_run=True) == 0
    assert not output_parent.exists()
    stdout = capsys.readouterr().out
    assert "reason=invalid_signal_class ref=skill_signals.jsonl:L2" in stdout
    assert "reason=invalid_skill ref=skill_signals.jsonl:L3" in stdout
    assert "reason=unknown_skill ref=skill_signals.jsonl:L4" in stdout


def test_full_cli_dry_run_existing_outputs_are_byte_identical(tmp_path, monkeypatch):
    logs = tmp_path / "consumer" / "logs"
    logs.mkdir(parents=True)
    state = tmp_path / "consumer" / "run_state"
    _write_jsonl(state / "skill_signals.jsonl", [
        {"signal_class": "misuse", "skill": "fallback"},
    ])
    output_parent = tmp_path / "existing"
    output_parent.mkdir()
    outputs = tuple(output_parent / name for name in ("narratives.jsonl", "edges.jsonl", "drift.jsonl"))
    for index, path in enumerate(outputs, 1):
        path.write_bytes(f"sentinel-{index}\n".encode())
    before = [path.read_bytes() for path in outputs]

    assert _run_cli(monkeypatch, logs, state, outputs, dry_run=True) == 0
    assert [path.read_bytes() for path in outputs] == before


def test_full_cli_apply_preserves_valid_mapping_and_repeated_noop(tmp_path, monkeypatch):
    logs = tmp_path / "consumer" / "logs"
    logs.mkdir(parents=True)
    state = tmp_path / "consumer" / "run_state"
    _write_jsonl(state / "skill_signals.jsonl", [
        {"signal_class": "misuse", "skill": "fallback", "evidence": "used another path"},
    ])
    outputs = tuple(tmp_path / "apply" / name for name in
                    ("narratives.jsonl", "edges.jsonl", "drift.jsonl"))

    assert _run_cli(monkeypatch, logs, state, outputs, dry_run=False) == 0
    drift_rows = [json.loads(line) for line in outputs[2].read_text().splitlines()]
    assert len(drift_rows) == 1
    assert drift_rows[0]["status_observed"] == "diverged"
    assert drift_rows[0]["ref"] == "skill_signals.jsonl:L1 task=signal_L1"
    before = [path.read_bytes() for path in outputs]

    assert _run_cli(monkeypatch, logs, state, outputs, dry_run=False) == 0
    assert [path.read_bytes() for path in outputs] == before


def test_signal_report_is_bounded_and_deterministic(tmp_path, monkeypatch, capsys):
    logs = tmp_path / "consumer" / "logs"
    logs.mkdir(parents=True)
    state = tmp_path / "consumer" / "run_state"
    _write_jsonl(state / "skill_signals.jsonl", [
        {"signal_class": "invalid", "skill": "validate"} for _ in range(25)
    ])
    outputs = tuple(tmp_path / "absent" / name for name in
                    ("narratives.jsonl", "edges.jsonl", "drift.jsonl"))

    assert _run_cli(monkeypatch, logs, state, outputs, dry_run=True) == 0
    stdout = capsys.readouterr().out
    assert "ref=skill_signals.jsonl:L20" in stdout
    assert "ref=skill_signals.jsonl:L21" not in stdout
    assert "signal report omitted 5 additional row(s); limit=20" in stdout
