#!/usr/bin/env python3
"""Projection contracts for first-class Derrick/Oracle verdict actors."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import project_summary as ps  # noqa: E402
import project_pages as pp  # noqa: E402


def test_closed_structured_actors_have_stable_identity_and_no_upgraded_auth():
    derrick = ps.project_actor({
        "agent_id": "ignored-legacy-value",
        "actor": {"id": "derrick", "type": "human",
                  "authentication": "ui-asserted",
                  "cryptographically_authenticated": False},
    })
    oracle = ps.project_actor({
        "actor": {"id": "oracle", "type": "agent",
                  "authentication": "ui-asserted",
                  "cryptographically_authenticated": False},
    })

    assert derrick == {
        "id": "derrick", "type": "human", "kind": "human",
        "hue": "--agent-derrick", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
        "source": "structured_ui_assertion",
    }
    assert oracle == {
        "id": "oracle", "type": "agent", "kind": "steward",
        "hue": "--agent-oracle", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
        "source": "structured_ui_assertion",
    }


def test_legacy_human_is_retained_but_has_no_invented_authentication():
    actor = ps.project_actor({"agent_id": "human:decross1"})
    assert actor["id"] == "human:decross1"
    assert actor["type"] == actor["kind"] == "human"
    assert actor["authentication"] is None
    assert actor["cryptographically_authenticated"] is None
    assert actor["source"] == "legacy_agent_id"


def test_closed_actor_schema_is_exact_and_non_dict_rows_fail_closed():
    malformed_rows = [
        None,
        [],
        {"agent_id": "derrick", "actor": {"id": "derrick", "type": "agent",
                                               "authentication": "ui-asserted",
                                               "cryptographically_authenticated": False}},
        {"actor": {"id": "derrick", "type": "human", "authentication": "claimed",
                    "cryptographically_authenticated": False}},
        {"actor": {"id": "oracle", "type": "agent", "authentication": "ui-asserted",
                    "cryptographically_authenticated": True}},
        {"actor": {"id": "oracle", "type": "agent", "authentication": "ui-asserted",
                    "cryptographically_authenticated": 0}},
    ]
    for row in malformed_rows:
        malformed = ps.project_actor(row)
        assert malformed["id"] == "unknown:malformed-actor"
        assert malformed["source"] == "malformed_structured_actor"
        assert malformed["authentication"] is None
        assert malformed["cryptographically_authenticated"] is None


def test_unrecognized_structured_actor_is_bounded_and_never_authentication_proof():
    arbitrary = ps.project_actor({
        "actor": {"id": "mallory-" + "x" * 500, "type": "human",
                  "authentication": "claimed", "cryptographically_authenticated": True},
    })
    assert arbitrary["id"].startswith("unrecognized:mallory-")
    assert len(arbitrary["id"]) <= ps._ACTOR_PRESENTATION_MAX
    assert arbitrary["source"] == "unrecognized_structured_actor"
    assert arbitrary["authentication"] is None
    assert arbitrary["cryptographically_authenticated"] is None


def test_legacy_closed_scalar_is_explicitly_unverified_not_upgraded():
    for raw in ("derrick", "oracle"):
        actor = ps.project_actor({"agent_id": raw})
        assert actor["id"] == f"legacy-unverified:{raw}"
        assert actor["type"] == actor["kind"] == "unknown"
        assert actor["authentication"] is None
        assert actor["cryptographically_authenticated"] is None
        assert actor["source"] == "legacy_closed_identity_unverified"


def test_actor_actions_are_first_class_agent_presence():
    derrick = ps.project_actor({"actor": {
        "id": "derrick", "type": "human", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    }})
    oracle = ps.project_actor({"actor": {
        "id": "oracle", "type": "agent", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    }})
    legacy = ps.project_actor({"agent_id": "human:decross1"})
    malformed = ps.project_actor({"actor": {"id": "derrick", "type": "agent"}})

    agents, _matrix, _attributions = ps.build_agents_and_matrix(
        [], [], [], [
            ("2026-08-18T01:00:00Z", derrick),
            ("2026-08-18T02:00:00Z", oracle),
            ("2026-08-18T03:00:00Z", legacy),
            ("2026-08-18T04:00:00Z", malformed),
        ], set(), "2026-08-12", "2026-08-18",
    )
    by_id = {agent["id"]: agent for agent in agents}
    assert by_id["derrick"]["kind"] == "human"
    assert by_id["derrick"]["hue"] == "--agent-derrick"
    assert by_id["oracle"]["kind"] == "steward"
    assert by_id["oracle"]["hue"] == "--agent-oracle"
    assert by_id["oracle"]["cryptographically_authenticated"] is False
    assert by_id["human:decross1"]["authentication"] is None
    assert by_id["unknown:malformed-actor"]["actor_source"] == "malformed_structured_actor"


def test_later_enactment_keeps_governing_verdict_actor_separate():
    first = {
        "timestamp": "2026-08-01T00:00:00Z", "proposal_id": "P-910",
        "status": "open", "target_type": "skill", "target": "validate",
        "title": "A truthful lifecycle", "change": "x",
    }
    accepted = {
        "timestamp": "2026-08-02T00:00:00Z", "proposal_id": "P-910",
        "agent_id": "derrick", "status": "closed", "verdict": "accepted",
        "actor": {"id": "derrick", "type": "human",
                  "authentication": "ui-asserted",
                  "cryptographically_authenticated": False},
    }
    enactment = {
        "timestamp": "2026-08-03T00:00:00Z", "proposal_id": "P-910",
        "status": "enacted",
    }
    proposal = {"first": first, "latest": enactment,
                "lifecycle": [first, accepted, enactment]}

    loop = ps.build_loop({"P-910": proposal}, [], [], [], "2026-08-18")
    chain = loop["chains"][0]
    assert chain["governing_verdict_actor"]["id"] == "derrick"
    assert chain["lifecycle"][1]["actor"] == "derrick"
    assert chain["lifecycle"][2]["actor"] == "unknown"
    # The later row is not falsely attributed to Derrick, but it keeps the
    # governing decision visibly linked to Derrick's asserted verdict.
    assert chain["lifecycle"][2]["governing_verdict_actor"]["id"] == "derrick"


def test_graph_agent_detail_displays_attribution_with_escaping():
    graph = (REPO / "memory" / "brain" / "view" / "graph.html").read_text()
    assert 'U.kv("actor source", esc(a.actor_source || "unknown"))' in graph
    assert 'U.kv("authentication", esc(auth))' in graph
    assert 'U.kv("cryptographic auth", esc(crypto))' in graph
    assert '? "unsupported claim" : "unknown"' in graph
    assert '? "yes" : "unknown"' not in graph


def test_shared_jsonl_loader_quarantines_non_object_rows_before_projection(
    tmp_path, capsys,
):
    ledger = tmp_path / "mixed.jsonl"
    ledger.write_text('{"proposal_id":"P-1"}\n["not", "a record"]\n42\nnull\n')

    rows = pp.load_jsonl(ledger)

    assert rows == [{"proposal_id": "P-1", "_source_line": 1}]
    stderr = capsys.readouterr().err
    assert "mixed.jsonl:2 non-object JSON row (list) skipped" in stderr
    assert "mixed.jsonl:3 non-object JSON row (int) skipped" in stderr
    assert "mixed.jsonl:4 non-object JSON row (NoneType) skipped" in stderr
