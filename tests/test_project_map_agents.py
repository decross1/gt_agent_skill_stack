"""The framework map retains inferred historical usage without a consumer."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_map as pm


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
