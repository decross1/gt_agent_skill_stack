"""The framework map retains inferred historical usage without a consumer."""
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
