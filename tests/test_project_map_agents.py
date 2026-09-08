"""The framework map retains inferred historical usage without a consumer."""
import hashlib
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_map as pm


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _skill(name):
    return {
        "name": name, "pack": "core", "runtime_safe": "true",
        "layer": "A", "description": "fixture skill",
    }


def _proposal(pid, target, reference):
    return {
        "timestamp": "2026-06-28T01:16:35+00:00",
        "proposal_id": pid,
        "agent_id": "draft:auto",
        "title": f"fixture {pid}",
        "target_type": "skill",
        "target": target,
        "change": "fixture change",
        "reasoning": "fixture reasoning",
        "references": [reference, target],
        "status": "draft",
    }


def _becomes(result):
    return {
        (edge["src"], edge["dst"])
        for edge in result["edges"]
        if edge["type"] == "becomes"
    }


def _becomes_with_sources(result):
    return {
        (edge["src"], edge["dst"], edge["source_ref"])
        for edge in result["edges"]
        if edge["type"] == "becomes"
    }


def _becomes_with_reference_sets(result):
    return {
        (edge["src"], edge["dst"], tuple(edge["source_refs"]))
        for edge in result["edges"]
        if edge["type"] == "becomes"
    }


@pytest.fixture
def framework(tmp_path, monkeypatch):
    for name in ("EDGES", "NARRATIVES", "PROPOSALS", "FEEDBACK",
                 "SPAWN_LEDGER", "FW_DECISIONS", "FW_RUN", "CONFORMANCE"):
        monkeypatch.setattr(pm, name, tmp_path / name)
    monkeypatch.setattr(pm, "PAGES_DIR", tmp_path / "pages")
    monkeypatch.setattr(pm, "load_skills", lambda: [
        {"name": "validate", "pack": "core", "runtime_safe": "true",
         "layer": "A", "description": "fixture skill"},
    ])
    monkeypatch.setattr(pm, "load_rules", lambda: [])
    monkeypatch.setattr(pm, "resolve_consumer", lambda: None)
    pm.FEEDBACK.write_text(json.dumps({
        "harvest_id": "fixture", "skill": "validate", "date": "2026-06-28",
    }) + "\n")
    return tmp_path


@pytest.mark.parametrize("consumer", ["none", "empty"])
def test_historical_usage_is_not_pruned_without_consumer_presence(framework, monkeypatch, consumer):
    if consumer == "empty":
        empty = framework / "consumer"
        empty.mkdir()
        monkeypatch.setattr(pm, "resolve_consumer", lambda: empty)
    before = {p: p.read_bytes() for p in framework.rglob("*") if p.is_file()}
    result = pm.build_map()
    nodes = {n["id"]: n for n in result["nodes"]}
    assert "agent-nara" in nodes
    assert "date" not in nodes["agent-nara"]
    edge = next(e for e in result["edges"] if e["type"] == "used")
    assert edge == {"src": "agent-nara", "dst": "skill-validate",
                    "type": "used", "weight_i": 1, "agent": "nara"}
    card = result["cards"]["agent-nara"]
    assert card["date"] == ""
    assert "inferred" in card["one_line"].lower()
    assert "historical" in card["one_line"].lower()
    assert "no recorded run" in card["one_line"].lower()
    assert all(e["src"] in nodes and e["dst"] in nodes for e in result["edges"])
    assert before == {p: p.read_bytes() for p in framework.rglob("*") if p.is_file()}


def test_unknown_harvest_skill_does_not_create_presence(framework):
    pm.FEEDBACK.write_text(json.dumps({
        "harvest_id": "fixture", "skill": "unknown", "date": "2026-06-28",
    }) + "\n")
    result = pm.build_map()
    assert not any(n["id"] == "agent-nara" for n in result["nodes"])
    assert not any(e["type"] == "used" for e in result["edges"])


def test_historical_reference_keeps_recorded_presence_and_explicit_weight(framework):
    pm.FW_RUN.write_text(json.dumps({
        "timestamp": "2026-08-02T01:00:00Z", "agent": "nara",
        "skill_used": "validate", "task_id": "fixture", "status": "passed",
    }) + "\n")
    with_reference = pm.build_map()
    pm.FEEDBACK.write_text("")
    without_reference = pm.build_map()
    assert with_reference["cards"]["agent-nara"] == without_reference["cards"]["agent-nara"]
    assert next(n for n in with_reference["nodes"] if n["id"] == "agent-nara") == next(
        n for n in without_reference["nodes"] if n["id"] == "agent-nara")
    edge = next(e for e in with_reference["edges"] if e["type"] == "used")
    assert edge["weight_e"] == 1 and edge["weight_i"] == 1


def test_structured_h008_d042_references_join_their_exact_findings(
        framework, monkeypatch):
    monkeypatch.setattr(
        pm, "load_skills",
        lambda: [_skill("decision-log"), _skill("orchestrate"),
                 _skill("experiment")],
    )
    _write_jsonl(pm.FEEDBACK, [
        {"harvest_id": "H008", "skill": "decision-log",
         "class": "confirmed", "date": "2026-06-14",
         "ref": "D-030,D-033"},
        {"harvest_id": "H008", "skill": "orchestrate",
         "class": "friction", "date": "2026-06-14", "ref": "D-042"},
        {"harvest_id": "H008", "skill": "experiment",
         "class": "friction", "date": "2026-06-14", "ref": "D-042"},
    ])
    _write_jsonl(pm.PROPOSALS, [
        _proposal("P-022", "orchestrate", "feedback.jsonl:H008:D-042"),
        _proposal("P-023", "experiment", "feedback.jsonl:H008:D-042"),
    ])
    before = {p: p.read_bytes() for p in framework.rglob("*") if p.is_file()}

    result = pm.build_map()

    assert _becomes(result) == {
        ("harvest-h008-l2", "proposal-p-022"),
        ("harvest-h008-l3", "proposal-p-023"),
    }
    assert _becomes_with_sources(result) == {
        ("harvest-h008-l2", "proposal-p-022",
         "feedback.jsonl:H008:D-042"),
        ("harvest-h008-l3", "proposal-p-023",
         "feedback.jsonl:H008:D-042"),
    }
    assert _becomes_with_reference_sets(result) == {
        ("harvest-h008-l2", "proposal-p-022",
         ("feedback.jsonl:H008:D-042",)),
        ("harvest-h008-l3", "proposal-p-023",
         ("feedback.jsonl:H008:D-042",)),
    }
    assert all("source_ref" not in edge for edge in result["edges"]
               if edge["type"] != "becomes")
    assert all("source_refs" not in edge for edge in result["edges"]
               if edge["type"] != "becomes")
    assert not any(edge["type"] in {"enacts", "produces"}
                   and edge["src"].startswith("harvest-h008")
                   for edge in result["edges"])
    assert before == {p: p.read_bytes() for p in framework.rglob("*") if p.is_file()}


def test_structured_harvest_reference_preserves_the_complete_suffix(
        framework, monkeypatch):
    monkeypatch.setattr(pm, "load_skills", lambda: [_skill("validate")])
    _write_jsonl(pm.FEEDBACK, [
        {"harvest_id": "H009", "skill": "validate", "class": "friction",
         "date": "2026-06-14", "ref": "D-042"},
        {"harvest_id": "H009", "skill": "validate", "class": "friction",
         "date": "2026-06-14", "ref": "D-042:appendix:A"},
    ])
    _write_jsonl(pm.PROPOSALS, [
        _proposal("P-100", "validate",
                  "feedback.jsonl:H009:D-042:appendix:A"),
        _proposal("P-101", "validate", "feedback.jsonl:H009:D-04"),
    ])

    result = pm.build_map()
    assert _becomes(result) == {
        ("harvest-h009-l2", "proposal-p-100"),
    }
    assert _becomes_with_sources(result) == {
        ("harvest-h009-l2", "proposal-p-100",
         "feedback.jsonl:H009:D-042:appendix:A"),
    }


def test_coalesced_finding_citations_retain_all_exact_references_deterministically(
        framework, monkeypatch):
    monkeypatch.setattr(pm, "load_skills", lambda: [_skill("validate")])
    _write_jsonl(pm.FEEDBACK, [{
        "harvest_id": "H999", "skill": "validate", "class": "friction",
        "date": "2026-06-14", "ref": "D-042:appendix:A",
    }])
    short = "feedback.jsonl:H999"
    structured = "feedback.jsonl:H999:D-042:appendix:A"
    proposal = _proposal("P-999", "validate", short)
    forward_references = [short, short, structured]
    proposal["references"] = forward_references
    _write_jsonl(pm.PROPOSALS, [proposal])
    before_forward = {
        path: path.read_bytes() for path in framework.rglob("*") if path.is_file()
    }

    forward = pm.build_map()
    assert before_forward == {
        path: path.read_bytes() for path in framework.rglob("*") if path.is_file()
    }
    reversed_references = list(reversed(forward_references))
    assert reversed_references != forward_references
    proposal["references"] = reversed_references
    _write_jsonl(pm.PROPOSALS, [proposal])
    before_reverse = {
        path: path.read_bytes() for path in framework.rglob("*") if path.is_file()
    }
    reversed_result = pm.build_map()
    assert before_reverse == {
        path: path.read_bytes() for path in framework.rglob("*") if path.is_file()
    }

    expected = {
        "src": "harvest-h999-l1",
        "dst": "proposal-p-999",
        "type": "becomes",
        "weight_e": 3,
        "source_ref": short,
        "source_refs": [short, structured],
    }
    assert [edge for edge in forward["edges"] if edge["type"] == "becomes"] == [expected]
    assert [edge for edge in reversed_result["edges"] if edge["type"] == "becomes"] == [expected]
    assert set(expected["source_refs"]) == {short, structured}


def test_becomes_weight_aggregates_citations_and_direct_typed_support(
        framework, monkeypatch):
    monkeypatch.setattr(pm, "load_skills", lambda: [_skill("validate")])
    _write_jsonl(pm.FEEDBACK, [{
        "harvest_id": "H999", "skill": "validate", "class": "friction",
        "date": "2026-06-14", "ref": "D-042:appendix:A",
    }])
    short = "feedback.jsonl:H999"
    structured = "feedback.jsonl:H999:D-042:appendix:A"
    proposal = _proposal("P-999", "validate", short)
    proposal["references"] = [short, structured]
    _write_jsonl(pm.PROPOSALS, [proposal])
    _write_jsonl(pm.EDGES, [{
        "src": "harvest-h999-l1",
        "dst": "proposal-p-999",
        "type": "becomes",
    }])
    before = {
        path: path.read_bytes() for path in framework.rglob("*") if path.is_file()
    }

    result = pm.build_map()

    assert before == {
        path: path.read_bytes() for path in framework.rglob("*") if path.is_file()
    }
    assert [edge for edge in result["edges"] if edge["type"] == "becomes"] == [{
        "src": "harvest-h999-l1",
        "dst": "proposal-p-999",
        "type": "becomes",
        "weight_e": 3,
        "source_ref": short,
        "source_refs": [short, structured],
    }]


def test_harvest_reference_rejects_malformed_and_ambiguous_identities(
        framework, monkeypatch):
    monkeypatch.setattr(pm, "load_skills", lambda: [_skill("validate")])
    _write_jsonl(pm.FEEDBACK, [
        {"harvest_id": "H010", "skill": "validate", "class": "friction",
         "date": "2026-06-14", "ref": "D-042"},
        {"harvest_id": "H010", "skill": "validate", "class": "gap",
         "date": "2026-06-14", "ref": "D-042"},
        {"harvest_id": "H011", "skill": "validate", "class": "friction",
         "date": "2026-06-14", "ref": "D-043"},
    ])
    _write_jsonl(pm.PROPOSALS, [
        _proposal("P-110", "validate", "feedback.jsonl:H010:D-042"),
        _proposal("P-111", "validate", "feedback.jsonl:H010"),
        _proposal("P-112", "validate", "feedback.jsonl:H011:"),
        _proposal("P-113", "validate", "feedback.jsonl::D-043"),
        _proposal("P-114", "validate",
                  "feedback.jsonl:H011:D-043:extra"),
    ])

    assert _becomes(pm.build_map()) == set()


def test_legacy_harvest_reference_keeps_exact_and_skill_disambiguated_joins(
        framework, monkeypatch):
    monkeypatch.setattr(
        pm, "load_skills",
        lambda: [_skill("validate"), _skill("orchestrate")],
    )
    _write_jsonl(pm.FEEDBACK, [
        {"harvest_id": "H012", "skill": "validate", "class": "confirmed",
         "date": "2026-06-14", "ref": "D-044"},
        {"harvest_id": "H013", "skill": "orchestrate", "class": "friction",
         "date": "2026-06-14", "ref": "D-045"},
        {"harvest_id": "H013", "skill": "validate", "class": "gap",
         "date": "2026-06-14", "ref": "D-046"},
    ])
    _write_jsonl(pm.PROPOSALS, [
        _proposal("P-120", "orchestrate", "feedback.jsonl:H012"),
        _proposal("P-121", "validate", "feedback.jsonl:H013"),
    ])

    result = pm.build_map()
    assert _becomes(result) == {
        ("harvest-h012-l1", "proposal-p-120"),
        ("harvest-h013-l3", "proposal-p-121"),
    }
    assert _becomes_with_sources(result) == {
        ("harvest-h012-l1", "proposal-p-120", "feedback.jsonl:H012"),
        ("harvest-h013-l3", "proposal-p-121", "feedback.jsonl:H013"),
    }


class _OneReadPath:
    """A path-shaped bounded source that fails if one capture reads twice."""

    def __init__(self, raw=b"", *, unreadable=False):
        self.raw = raw
        self.unreadable = unreadable
        self.reads = 0

    def open(self, mode="r"):
        assert mode == "rb"
        self.reads += 1
        assert self.reads == 1
        if self.unreadable:
            raise OSError("synthetic unreadable source")
        return io.BytesIO(self.raw)

    def __str__(self):
        return "synthetic-source"


def _rows_bytes(rows):
    return b"".join(
        json.dumps(row, separators=(",", ":")).encode("utf-8") + b"\n"
        for row in rows
    )


def test_recorded_work_maps_only_explicit_fields_from_once_read_sources(
        framework, monkeypatch):
    run_raw = _rows_bytes([
        {"task_id": "review", "status": "assigned", "agent": "planner",
         "dependencies": []},
        {"task_id": "check", "status": "reported complete",
         "parent_task_id": "review", "skill_used": "validate",
         "dependencies": ["review"]},
    ])
    spawn_raw = _rows_bytes([
        {"spawn_id": "delegation", "status": "launched", "agent": "builder",
         "child_task_id": "check", "contract": {"skill_subset": ["validate"]},
         "dependencies": []},
    ])
    run_source = _OneReadPath(run_raw)
    spawn_source = _OneReadPath(spawn_raw)
    monkeypatch.setattr(pm, "FW_RUN", run_source)
    monkeypatch.setattr(pm, "SPAWN_LEDGER", spawn_source)
    monkeypatch.setattr(pm, "_capture_time", lambda: "2026-09-07T23:00:00Z")

    result = pm.build_map()

    assert run_source.reads == spawn_source.reads == 1
    assert "work_capture" not in result
    work = result["work"]
    assert work["schema_version"] == "work-graph/v1"
    assert work["dependency_availability"] == {"state": "available", "reason": None}
    assert work["source"] == {
        "namespace": "agent_system/framework",
        "locator": "framework:run-and-spawn",
        "capture_basis": {
            "captured_at": "2026-09-07T23:00:00Z",
            "atomic": False,
            "limits": {"file_bytes": 1_048_576, "file_rows": 2_048,
                       "row_bytes": 65_536, "json_container_depth": 64},
            "files": [
                {"locator": "run_state/framework.run.jsonl",
                 "sha256": hashlib.sha256(run_raw).hexdigest(),
                 "bytes": len(run_raw), "rows": 2,
                 "availability": "available"},
                {"locator": "run_state/spawn.jsonl",
                 "sha256": hashlib.sha256(spawn_raw).hexdigest(),
                 "bytes": len(spawn_raw), "rows": 1,
                 "availability": "available"},
            ],
        },
    }
    by_record = {node.get("record_id"): node for node in work["nodes"]
                 if node["type"] == "work"}
    assert set(by_record) == {"review", "check", "delegation"}
    assert by_record["review"]["role"] == "planner"
    assert by_record["delegation"]["source_locator"] == \
        "run_state/spawn.jsonl:L1"
    endpoints = {(edge["type"], edge["source"], edge["target"])
                 for edge in work["edges"]}
    assert ("parent", by_record["review"]["id"], by_record["check"]["id"]) \
        in endpoints
    assert ("dependency", by_record["check"]["id"], by_record["review"]["id"]) \
        in endpoints
    assert ("spawn_assignment", by_record["delegation"]["id"],
            by_record["check"]["id"]) in endpoints
    assert {edge["type"] for edge in work["edges"]} == {
        "parent", "dependency", "spawn_assignment", "allowed_skill",
        "observed_skill",
    }
    assert pm._encoded_json_bytes(work) < pm.WORK_MAX_BYTES
    assert pm._encoded_json_bytes({k: v for k, v in result.items()
                                   if k not in {"work", "work_capture"}}) \
        < pm.MAX_BYTES
    assert pm._encoded_json_bytes(result) < pm.MAX_TOTAL_BYTES


@pytest.mark.parametrize("case,reason", [
    ("unreadable", "source_unreadable"),
    ("malformed", "malformed_jsonl"),
    ("non_object", "non_object_json"),
    ("file_bytes", "file_byte_cap_exceeded"),
    ("file_rows", "file_row_cap_exceeded"),
    ("row_bytes", "row_byte_cap_exceeded"),
])
def test_invalid_or_overflowed_capture_omits_work_with_exact_failure_envelope(
        framework, monkeypatch, capsys, case, reason):
    if case == "unreadable":
        run_source = _OneReadPath(unreadable=True)
    elif case == "malformed":
        run_source = _OneReadPath(b'{"task_id":\n')
    elif case == "non_object":
        run_source = _OneReadPath(b"[]\n")
    elif case == "file_bytes":
        run_source = _OneReadPath(b" " * (1_048_576 + 1))
    elif case == "file_rows":
        run_source = _OneReadPath(b"{}\n" * (2_048 + 1))
    else:
        run_source = _OneReadPath(
            b'{"task_id":"' + (b"x" * 65_536) + b'"}\n')
    spawn_raw = _rows_bytes([{"spawn_id": "still-valid", "status": "recorded"}])
    spawn_source = _OneReadPath(spawn_raw)
    monkeypatch.setattr(pm, "FW_RUN", run_source)
    monkeypatch.setattr(pm, "SPAWN_LEDGER", spawn_source)
    monkeypatch.setattr(pm, "_capture_time", lambda: "2026-09-07T23:01:00Z")

    result = pm.build_map()

    assert run_source.reads == spawn_source.reads == 1
    assert "work" not in result
    failure = result["work_capture"]
    assert failure["state"] == "unavailable"
    assert failure["reason"] == "framework_source_unavailable"
    files = failure["source"]["capture_basis"]["files"]
    assert files[0]["locator"] == "run_state/framework.run.jsonl"
    assert files[0]["availability"] == "unavailable"
    assert files[0]["reason"] == reason
    assert files[1]["availability"] == "available"
    if case == "file_bytes":
        assert files[0]["sha256"] is None and files[0]["bytes"] is None
        assert files[0]["captured_prefix_bytes"] == 1_048_577
        assert len(files[0]["captured_prefix_sha256"]) == 64
    assert reason in capsys.readouterr().err


def test_recorded_work_withholds_duplicate_ids_and_keeps_self_assignment_qualified(
        framework, monkeypatch):
    run_source = _OneReadPath(_rows_bytes([
        {"task_id": "duplicate", "status": "same"},
        {"task_id": "duplicate", "status": "same"},
    ]))
    spawn_source = _OneReadPath(_rows_bytes([
        {"spawn_id": "self", "status": "recorded", "child_task_id": "self",
         "contract": {"skill_subset": ["validate"]}},
    ]))
    monkeypatch.setattr(pm, "FW_RUN", run_source)
    monkeypatch.setattr(pm, "SPAWN_LEDGER", spawn_source)
    monkeypatch.setattr(pm, "_capture_time", lambda: "2026-09-07T23:02:00Z")

    work = pm.build_map()["work"]

    assert work["projection_state"] == {
        "state": "partial", "reason": "unresolved_references"}
    assert work["dependency_availability"] == {
        "state": "unavailable", "reason": "dependencies_not_supplied"}
    assert not any(node.get("record_id") == "duplicate" for node in work["nodes"])
    assert any(row["reason"] == "conflicting_id"
               and row["record_id"] == "duplicate"
               for row in work["unresolved"])
    assignment = [edge for edge in work["edges"]
                  if edge["type"] == "spawn_assignment"]
    assert len(assignment) == 1
    assert assignment[0]["source"] == assignment[0]["target"]
    assert not any(edge["type"] == "dependency" for edge in work["edges"])


def test_recorded_work_encoded_byte_cap_is_enforced_inside_build_map(
        framework, monkeypatch, capsys):
    monkeypatch.setattr(
        pm, "FW_RUN",
        _OneReadPath(_rows_bytes([{"task_id": "bounded", "status": "recorded"}])),
    )
    monkeypatch.setattr(pm, "SPAWN_LEDGER", _OneReadPath(b""))
    monkeypatch.setattr(pm, "_capture_time", lambda: "2026-09-07T23:02:30Z")
    monkeypatch.setattr(pm, "WORK_MAX_BYTES", 1)

    result = pm.build_map()

    assert "work" not in result
    assert result["work_capture"]["reason"] == "work_output_byte_cap_exceeded"
    assert result["work_capture"]["limits"]["observed_work_bytes"] > 1
    error = capsys.readouterr().err
    assert "recorded work unavailable: output" in error
    assert "cap 1 B" in error


def test_emit_ignores_only_capture_timestamp_and_keeps_content_changes(
        framework, monkeypatch, tmp_path):
    raw = _rows_bytes([{"task_id": "one", "status": "first"}])
    monkeypatch.setattr(pm, "FW_RUN", _OneReadPath(raw))
    monkeypatch.setattr(pm, "SPAWN_LEDGER", _OneReadPath(b""))
    times = iter(["2026-09-07T23:03:00Z", "2026-09-07T23:04:00Z",
                  "2026-09-07T23:05:00Z"])
    monkeypatch.setattr(pm, "_capture_time", lambda: next(times))
    monkeypatch.setattr(pm, "OUT_JS", tmp_path / "map_data.js")
    first = pm.build_map()
    assert pm.emit(first) is True

    monkeypatch.setattr(pm, "FW_RUN", _OneReadPath(raw))
    monkeypatch.setattr(pm, "SPAWN_LEDGER", _OneReadPath(b""))
    second = pm.build_map()
    assert first["work"]["source"]["capture_basis"]["captured_at"] != \
        second["work"]["source"]["capture_basis"]["captured_at"]
    assert pm.emit(second) is False

    changed = _rows_bytes([{"task_id": "one", "status": "second"}])
    monkeypatch.setattr(pm, "FW_RUN", _OneReadPath(changed))
    monkeypatch.setattr(pm, "SPAWN_LEDGER", _OneReadPath(b""))
    third = pm.build_map()
    assert pm.emit(third) is True
    assert "second" in pm.OUT_JS.read_text()


@pytest.mark.parametrize("depth", [65, 1005])
def test_capture_amendment_deep_json_is_unavailable(framework, monkeypatch, depth):
    raw = b'{"task_id":"x","status":' + b'[' * depth + b'0' + b']' * depth + b'}\n'
    run = _OneReadPath(raw)
    spawn = _OneReadPath(b'')
    monkeypatch.setattr(pm, "FW_RUN", run)
    monkeypatch.setattr(pm, "SPAWN_LEDGER", spawn)
    result = pm.build_map()
    assert "work" not in result
    failure = result["work_capture"]
    assert failure["state"] == "unavailable"
    source = failure["source"]["capture_basis"]["files"][0]
    assert source["reason"] == "json_nesting_exceeded"
    assert source["sha256"] == hashlib.sha256(raw).hexdigest()
    assert source["bytes"] == len(raw)
    assert run.reads == spawn.reads == 1


def test_capture_amendment_physical_row_before_strip(framework, monkeypatch):
    raw = b' ' * 65536 + b'{"task_id":"x"}\n'
    run = _OneReadPath(raw)
    monkeypatch.setattr(pm, "FW_RUN", run)
    monkeypatch.setattr(pm, "SPAWN_LEDGER", _OneReadPath(b''))
    result = pm.build_map()
    assert "work" not in result
    source = result["work_capture"]["source"]["capture_basis"]["files"][0]
    assert source["reason"] == "row_byte_cap_exceeded"
    assert source["sha256"] == hashlib.sha256(raw).hexdigest()
    assert source["bytes"] == len(raw)
