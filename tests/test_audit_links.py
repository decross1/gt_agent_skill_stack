"""Read-only pre-append checks against exact framework audit source bytes."""
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import project_pages as pp

HEAD = "2026-09-05"
TITLE = "D-AS003-TIMELINE-LABELS: classify recorded proposal appends"
WRONG = "d-as003-timeline-labels-classify-recorded-proposal-appends"


@pytest.fixture
def audit(tmp_path):
    memory = tmp_path / "memory"
    (memory / "brain").mkdir(parents=True)
    (memory / "DECISIONS.md").write_text(f"## {HEAD} — {TITLE}\n\nRecorded decision.\n")
    (memory / "brain/narratives.jsonl").write_text(json.dumps({
        "task_id": "AS003-completion", "type": "reflection",
        "agent_id": "oracle-agent-system",
    }) + "\n")
    return tmp_path


def module():
    return importlib.import_module("validate_audit_links")


def edge(**changes):
    return {
        "timestamp": "2026-09-05T03:30:01Z", "src": "as003-completion",
        "src_type": "reflection", "type": "references",
        "dst": pp.decision_slug(HEAD, "framework", TITLE), "dst_type": "decision",
        "source_event": "AS003-completion", "agent_id": "human:reported-label",
        **changes,
    }


def candidates(audit, *rows):
    path = audit / "pending.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def test_audit_resolver_reuses_projector_identity_and_exact_source_bytes(audit):
    result = module().resolve_decision(audit, HEAD, TITLE)
    assert result["slug"] == pp.load_decisions(audit / "memory/DECISIONS.md", "framework")[0]["slug"]
    assert result["slug"] != WRONG
    assert result["source_sha256"] == hashlib.sha256((audit / "memory/DECISIONS.md").read_bytes()).hexdigest()
    assert result["authority_verified"] is False


def test_audit_parser_extraction_preserves_loader_behavior(audit):
    path = audit / "memory/DECISIONS.md"
    path.write_text(path.read_text() + "\n## D-007 — A correction\n\n**Correction:** Keep history.\n2026-08-01\n")
    assert pp.parse_decisions(path.read_text(), "framework") == pp.load_decisions(path, "framework")
    assert pp.parse_decisions(path.read_text(), "framework")[1]["type"] == "correction"


@pytest.mark.parametrize("wrong", [WRONG, "missing-node", "dec-ap-foreign"])
def test_audit_rejects_mistyped_or_unexamined_destination(audit, wrong):
    path = candidates(audit, edge(dst=wrong))
    result = module().validate_candidates(audit, path)
    assert result["ok"] is False
    assert result["errors"][0]["line"] == 1
    assert result["errors"][0]["field"] == "dst"
    assert "unresolved" in result["errors"][0]["reason"]


def test_audit_valid_candidate_is_snapshot_check_without_writes_or_authority(audit):
    path = candidates(audit, edge())
    before = {p: p.read_bytes() for p in audit.rglob("*") if p.is_file()}
    result = module().validate_candidates(audit, path)
    assert result["ok"] is True
    assert result["checked"] == 1
    assert result["authority_verified"] is False
    assert result["append_performed"] is False
    assert result["candidate_sha256"] == hashlib.sha256(before[path]).hexdigest()
    assert before == {p: p.read_bytes() for p in audit.rglob("*") if p.is_file()}


@pytest.mark.parametrize("changes", [
    {"src_type": "decision"}, {"dst_type": "reflection"}, {"type": "delete"},
    {"src": []}, {"agent_id": ""}, {"source_event": None}, {"timestamp": 7},
])
def test_audit_malformed_or_mismatched_edge_fails_closed(audit, changes):
    assert module().validate_candidates(audit, candidates(audit, edge(**changes)))["ok"] is False


def test_audit_correction_append_does_not_retract_the_historical_bad_edge(audit):
    path = candidates(audit, edge(dst=WRONG), edge(), edge(type="supersedes"))
    result = module().validate_candidates(audit, path)
    assert result["ok"] is False
    assert result["checked"] == 3
    assert [e["line"] for e in result["errors"]] == [1]
    assert len(path.read_text().splitlines()) == 3


def test_audit_explicit_narrative_identity_override_is_preserved(audit):
    path = audit / "memory/brain/narratives.jsonl"
    row = json.loads(path.read_text())
    row.update(_slug="explicit-id", _type_override="anomaly")
    path.write_text(json.dumps(row) + "\n")
    result = module().validate_candidates(audit, candidates(audit, edge(src="explicit-id", src_type="anomaly")))
    assert result["ok"] is True


@pytest.mark.parametrize("title", ["missing", TITLE])
def test_audit_missing_or_ambiguous_decision_never_guesses(audit, title):
    if title == TITLE:
        path = audit / "memory/DECISIONS.md"
        path.write_text(path.read_text() * 2)
    with pytest.raises(ValueError):
        module().resolve_decision(audit, HEAD, title)


def test_audit_truncated_slug_collision_is_ambiguous(audit):
    path = audit / "memory/DECISIONS.md"
    path.write_text(path.read_text() + f"\n## {HEAD} — {TITLE} differently\n\nSecond choice.\n")
    with pytest.raises(ValueError, match="ambiguous"):
        module().resolve_decision(audit, HEAD, TITLE)
    result = module().validate_candidates(audit, candidates(audit, edge()))
    assert result["ok"] is False
    assert "ambiguous" in result["errors"][0]["reason"]


@pytest.mark.parametrize("bad", ["{bad json}\n", "[]\n", "\n"])
def test_audit_bad_candidate_file_fails_without_partial_success(audit, bad):
    path = audit / "pending.jsonl"
    path.write_text(bad)
    with pytest.raises(ValueError):
        module().validate_candidates(audit, path)


def test_audit_unreadable_source_is_not_empty_success(audit):
    (audit / "memory/brain/narratives.jsonl").unlink()
    with pytest.raises(OSError):
        module().validate_candidates(audit, candidates(audit, edge()))


def test_audit_cli_reports_bad_then_valid_pending_edge_without_appending(audit):
    path = candidates(audit, edge(dst=WRONG))
    cmd = [sys.executable, str(REPO / "scripts/validate_audit_links.py"),
           "--repo-root", str(audit), "check", "--edges", str(path)]
    bad = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["errors"][0]["line"] == 1
    path = candidates(audit, edge())
    good = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    assert good.returncode == 0
    assert json.loads(good.stdout)["append_performed"] is False


def test_audit_receipts_identify_caller_selected_root_and_resolved_paths(audit):
    pending = candidates(audit, edge())
    resolved = module().resolve_decision(audit, HEAD, TITLE)
    checked = module().validate_candidates(audit, pending)
    for result in (resolved, checked):
        assert result["repo_root"] == str(audit.resolve())
    assert resolved["source_path"] == str((audit / "memory/DECISIONS.md").resolve())
    assert checked["source_paths"]["memory/brain/narratives.jsonl"] == str((audit / "memory/brain/narratives.jsonl").resolve())
    assert checked["candidate_path"] == str(pending.resolve())


@pytest.mark.parametrize("suffix", [', "dst": "duplicate"', ', "extra": NaN'])
def test_audit_ambiguous_or_nonstandard_json_is_rejected(audit, suffix):
    pending = audit / "pending.jsonl"
    # Duplicate endpoint is valid last: ordinary json.loads would accept it.
    raw = json.dumps(edge())
    if "duplicate" in suffix:
        raw = '{"dst":"missing",' + raw[1:]
    else:
        raw = raw[:-1] + suffix + "}"
    pending.write_text(raw + "\n")
    with pytest.raises(ValueError, match="pending.jsonl:1"):
        module().validate_candidates(audit, pending)


def test_audit_cli_does_not_create_project_bytecode_without_environment_guard(audit):
    code = audit / "isolated-code"
    code.mkdir()
    for name in ("brain_ledger.py", "project_pages.py", "validate_audit_links.py"):
        shutil.copyfile(REPO / "scripts" / name, code / name)
    pending = candidates(audit, edge())
    before = {p: p.read_bytes() for p in audit.rglob("*") if p.is_file()}
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    env.pop("PYTHONPYCACHEPREFIX", None)
    result = subprocess.run(
        [sys.executable, str(code / "validate_audit_links.py"), "--repo-root",
         str(audit), "check", "--edges", str(pending)],
        env=env, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert before == {p: p.read_bytes() for p in audit.rglob("*") if p.is_file()}


@pytest.mark.parametrize("timestamp", [
    "not-a-time", "2026-02-30T12:00:00Z", "2026-09-05T25:00:00Z",
    "2026-09-05T12:61:00Z", "2026-09-05T12:00:00+01:99",
    "2026-09-05T12:00:60Z", "2026-09-05T12:00:00+24:00",
    "2025-02-29T12:00:00Z",
    "2026-09-05", "", None, 7, [], {},
])
def test_audit_timestamp_must_be_a_possible_recorded_datetime(audit, timestamp):
    pending = candidates(audit, edge(timestamp=timestamp))
    before = pending.read_bytes()
    result = module().validate_candidates(audit, pending)
    assert result["ok"] is False
    assert any(e["field"] == "timestamp" and e["line"] == 1 for e in result["errors"])
    assert pending.read_bytes() == before


@pytest.mark.parametrize("timestamp", [
    "2026-09-05T12:00:00Z", "2026-09-05T12:00:00.123+05:30",
    "2040-01-02T00:15:00+05:30", "2040-01-01T23:15:00-04:00",
    "2026-09-05 12:00:00+00:00", "2026-09-05T12:00:00",
    "2024-02-29T12:00:00+23:59",
])
def test_audit_valid_dates_and_compound_labels_do_not_establish_authentication(audit, timestamp):
    pending = candidates(audit, edge(timestamp=timestamp, source_event="task/substep:receipt-7"))
    result = module().validate_candidates(audit, pending)
    assert result["ok"] is True
    assert result["authority_verified"] is False
    assert "source_event" in result["limitation"]


def test_bad_time_and_endpoint_are_reported_independently(audit):
    result = module().validate_candidates(
        audit, candidates(audit, edge(timestamp="not-a-time", dst=WRONG)))
    assert result["ok"] is False
    assert {error["field"] for error in result["errors"]} == {"timestamp", "dst"}
