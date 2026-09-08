from __future__ import annotations

import builtins
from copy import deepcopy

import pytest

from scripts.work_graph import build_work_graph


SOURCE = {
    "namespace": "demo/run",
    "locator": "sealed://framework/run.jsonl",
    "capture_basis": {"sha256": "abc123", "mode": "exact-bytes"},
    "captured_at": "2026-09-07T18:00:00Z",
}


def _work_nodes(graph):
    return {node["record_id"]: node for node in graph["nodes"] if node["type"] == "work"}


def _skill_nodes(graph):
    return {node["skill_id"]: node for node in graph["nodes"] if node["type"] == "skill"}


def _edge_tuples(graph):
    return {(edge["type"], edge["source"], edge["target"]) for edge in graph["edges"]}


def test_projects_explicit_relations_raw_status_and_dependency_cycle():
    records = [
        {
            "id": "root",
            "kind": "agent",
            "source_locator": "sealed://framework/spawn.jsonl#root",
            "role": "parent",
            "raw_status": {"label": "complete", "running": True},
            "spawn_assignments": ["child"],
            "allowed_skills": ["gate-check"],
            "observed_skills": ["run-log"],
            "dependencies": ["child"],
        },
        {
            "id": "child",
            "kind": "agent",
            "role": "child",
            "raw_status": "halted",
            "parent_id": "root",
            "allowed_skills": ["run-log"],
            "observed_skills": ["gate-check"],
            "dependencies": ["root"],
        },
    ]
    before = deepcopy(records)

    graph = build_work_graph(records, source=SOURCE)

    assert records == before
    assert graph["schema_version"] == "work-graph/v1"
    assert graph["source"] == SOURCE
    assert graph["source"] is not SOURCE
    assert graph["projection_state"] == {"state": "complete", "reason": None}
    assert graph["dependency_availability"] == {"state": "available", "reason": None}

    work = _work_nodes(graph)
    skills = _skill_nodes(graph)
    for node in graph["nodes"]:
        assert node["source_metadata"] == SOURCE
        assert node["source_metadata"] is not SOURCE
    for edge in graph["edges"]:
        assert edge["source_metadata"] == SOURCE
        assert edge["source_metadata"] is not SOURCE
    assert work["root"]["id"] == "work:demo%2Frun:agent:root"
    assert work["root"]["source_locator"] == "sealed://framework/spawn.jsonl#root"
    assert work["child"]["source_locator"] == {
        "collection": "sealed://framework/run.jsonl",
        "record": {"kind": "agent", "id": "child"},
    }
    assert work["root"]["role"] == "parent"
    assert work["child"]["role"] == "child"
    assert work["root"]["raw_status"] == {"label": "complete", "running": True}
    assert work["child"]["raw_status"] == "halted"
    for node in work.values():
        assert {"status", "authenticated", "alive", "executing"}.isdisjoint(node)

    edges = _edge_tuples(graph)
    root = work["root"]["id"]
    child = work["child"]["id"]
    assert ("parent", root, child) in edges
    assert ("spawn_assignment", root, child) in edges
    assert ("dependency", root, child) in edges
    assert ("dependency", child, root) in edges
    assert ("allowed_skill", root, skills["gate-check"]["id"]) in edges
    assert ("observed_skill", root, skills["run-log"]["id"]) in edges
    observed = [edge for edge in graph["edges"] if edge["type"] == "observed_skill"]
    assert observed
    assert {edge["assertion_basis"] for edge in observed} == {"caller_supplied"}
    assert all("assertion_basis" not in edge for edge in graph["edges"] if edge["type"] != "observed_skill")
    assert graph["cycles"] == [{"type": "dependency", "node_ids": sorted([root, child])}]
    assert graph["unresolved"] == []


def test_exact_identity_and_deterministic_unresolved_duplicates_and_conflicts():
    duplicate = {
        "id": "dup",
        "kind": "task",
        "source_locator": "sealed://run#dup",
        "raw_status": "queued",
    }
    records = [
        {
            "id": "Case",
            "kind": "task",
            "source_locator": "sealed://run#Case",
            "dependencies": ["case", "ghost", "dup"],
            "spawn_assignments": ["conflict"],
        },
        {"id": "case", "kind": "task", "source_locator": "sealed://run#case"},
        {"kind": "task", "source_locator": "sealed://run#missing-id", "raw_status": "done"},
        duplicate,
        deepcopy(duplicate),
        {"id": "conflict", "kind": "task", "source_locator": "sealed://run#conflict-a", "raw_status": "a"},
        {"id": "conflict", "kind": "task", "source_locator": "sealed://run#conflict-b", "raw_status": "b"},
    ]

    first = build_work_graph(records, source=SOURCE)
    reordered = build_work_graph(list(reversed(records)), source=SOURCE)

    assert first == reordered
    assert set(_work_nodes(first)) == {"Case", "case"}
    reasons = {row["reason"] for row in first["unresolved"]}
    assert {"missing_id", "duplicate_id", "conflicting_id", "missing_target_id", "ambiguous_target_id"} <= reasons
    assert any(row["reason"] == "missing_id" and row["source_locator"] == "sealed://run#missing-id" for row in first["unresolved"])
    assert any(row["reason"] == "missing_target_id" and row["target_id"] == "ghost" for row in first["unresolved"])
    assert any(row["reason"] == "ambiguous_target_id" and row["target_id"] == "dup" for row in first["unresolved"])
    assert first["projection_state"]["state"] == "partial"

    later_source = deepcopy(SOURCE)
    later_source["captured_at"] = "2099-01-01T00:00:00Z"
    later = build_work_graph(records, source=later_source)
    assert [(node["id"], node.get("raw_status")) for node in first["nodes"]] == [
        (node["id"], node.get("raw_status")) for node in later["nodes"]
    ]
    assert "generated_at" not in later


def test_dependency_availability_distinguishes_absent_from_explicit_empty():
    absent = [
        {"id": "a", "kind": "task", "source_locator": "sealed://run#a"},
        {"id": "b", "kind": "task", "source_locator": "sealed://run#b"},
    ]
    explicit = [dict(record, dependencies=[]) for record in absent]

    absent_graph = build_work_graph(absent, source=SOURCE)
    explicit_graph = build_work_graph(explicit, source=SOURCE)

    assert absent_graph["dependency_availability"] == {
        "state": "unavailable",
        "reason": "dependencies_not_supplied",
    }
    assert explicit_graph["dependency_availability"] == {"state": "available", "reason": None}
    assert not [edge for edge in absent_graph["edges"] if edge["type"] == "dependency"]
    assert not [edge for edge in explicit_graph["edges"] if edge["type"] == "dependency"]


@pytest.mark.parametrize(
    ("records", "identity_reason"),
    [
        (
            [
                {"id": "same", "kind": "task", "dependencies": []},
                {"id": "same", "kind": "task", "dependencies": []},
            ],
            "duplicate_id",
        ),
        (
            [
                {"id": "same", "kind": "task", "dependencies": []},
                {"id": "same", "kind": "task", "dependencies": ["unknown"]},
            ],
            "conflicting_id",
        ),
        ([{"kind": "task", "dependencies": []}], "missing_id"),
        ([{"id": "missing-kind", "dependencies": []}], "missing_kind"),
    ],
)
def test_supplied_dependencies_on_withheld_identities_are_not_reported_absent(
        records, identity_reason):
    before = deepcopy(records)

    graph = build_work_graph(records, source=SOURCE)
    reordered = build_work_graph(list(reversed(records)), source=SOURCE)

    assert records == before
    assert graph == reordered
    assert graph["dependency_availability"] == {
        "state": "unavailable",
        "reason": "dependencies_identity_unresolved",
    }
    assert any(issue["reason"] == identity_reason for issue in graph["unresolved"])
    assert not graph["nodes"]
    assert not graph["edges"]


def test_dependency_availability_is_partial_for_projectable_and_withheld_evidence():
    records = [
        {"id": "kept", "kind": "task", "dependencies": []},
        {"id": "same", "kind": "task", "dependencies": []},
        {"id": "same", "kind": "task", "dependencies": []},
    ]
    before = deepcopy(records)

    graph = build_work_graph(records, source=SOURCE)
    reordered = build_work_graph(list(reversed(records)), source=SOURCE)
    capped = build_work_graph(records, source=SOURCE, node_cap=0, edge_cap=0)

    assert records == before
    assert graph == reordered
    assert graph["dependency_availability"] == {
        "state": "partial",
        "reason": "dependencies_partially_available",
    }
    assert set(_work_nodes(graph)) == {"kept"}
    assert not [edge for edge in graph["edges"] if edge["type"] == "dependency"]
    assert capped["dependency_availability"] == graph["dependency_availability"]
    assert capped["nodes"] == [] and capped["edges"] == []
    assert capped["limits"]["nodes_omitted"] == 1


def test_malformed_dependency_evidence_is_seen_before_identity_rejection():
    graph = build_work_graph(
        [{"kind": "task", "dependencies": "not-a-list"}],
        source=SOURCE,
    )

    assert graph["dependency_availability"] == {
        "state": "unavailable",
        "reason": "dependencies_invalid",
    }
    assert {issue["reason"] for issue in graph["unresolved"]} == {"missing_id"}


def test_spawn_self_assignment_remains_an_assignment_without_execution_claim():
    records = [{
        "id": "SP-self", "kind": "spawn", "raw_status": "assigned",
        "spawn_assignments": ["SP-self"],
    }]
    graph = build_work_graph(records, source=SOURCE)
    node_id = _work_nodes(graph)["SP-self"]["id"]

    assert _edge_tuples(graph) == {("spawn_assignment", node_id, node_id)}
    assert all(edge["type"] != "child_execution" for edge in graph["edges"])
    assert {"executing", "authenticated", "alive"}.isdisjoint(_work_nodes(graph)["SP-self"])


def test_cycle_diagnostics_describe_pre_cap_candidates():
    graph = build_work_graph(
        [{"id": "cycle", "kind": "task", "dependencies": ["cycle"]}],
        source=SOURCE,
        node_cap=0,
        edge_cap=0,
    )
    omitted_id = "work:demo%2Frun:task:cycle"

    assert graph["nodes"] == [] and graph["edges"] == []
    assert graph["cycles"] == [{"type": "dependency", "node_ids": [omitted_id]}]
    assert graph["limits"]["nodes_omitted"] == 1
    assert graph["limits"]["edges_omitted"] == 1
    assert graph["projection_state"] == {"state": "partial", "reason": "projection_truncated"}


def test_count_caps_are_explicit_and_source_overflow_fails_closed():
    records = [
        {
            "id": "a",
            "kind": "task",
            "spawn_assignments": ["b"],
            "allowed_skills": ["s1", "s2"],
            "dependencies": [],
        },
        {"id": "b", "kind": "task", "dependencies": []},
    ]

    capped = build_work_graph(records, source=SOURCE, node_cap=2, edge_cap=1)
    assert capped["limits"]["unit"] == "items"
    assert capped["limits"]["node_candidates"] == 4
    assert capped["limits"]["nodes_omitted"] == 2
    assert capped["limits"]["edge_candidates"] == 3
    assert capped["limits"]["edges_omitted"] == 2
    assert len(capped["nodes"]) == 2
    assert len(capped["edges"]) == 1
    assert capped["projection_state"] == {"state": "partial", "reason": "projection_truncated"}

    overflow = build_work_graph(records + [{"id": "c", "kind": "task"}], source=SOURCE, record_cap=2)
    assert overflow["nodes"] == []
    assert overflow["edges"] == []
    assert overflow["cycles"] == []
    assert overflow["projection_state"] == {"state": "unavailable", "reason": "record_cap_exceeded"}
    assert overflow["dependency_availability"] == {
        "state": "unavailable",
        "reason": "projection_unavailable",
    }
    assert overflow["limits"]["record_count"] == 3
    assert overflow["unresolved"] == [
        {"reason": "record_cap_exceeded", "record_count": 3, "record_cap": 2, "source_locator": SOURCE["locator"]}
    ]


def test_diagnostics_and_cycles_are_bounded_without_hiding_partial_projection():
    invalid = [
        {"kind": "task", "source_locator": f"sealed://run#missing-{number}"}
        for number in range(4)
    ]
    diagnostics = build_work_graph(invalid, source=SOURCE, diagnostic_cap=2)
    assert len(diagnostics["unresolved"]) == 2
    assert diagnostics["limits"]["unresolved_candidates"] == 4
    assert diagnostics["limits"]["unresolved_omitted"] == 2
    assert diagnostics["projection_state"] == {"state": "partial", "reason": "diagnostics_truncated"}

    cyclic = [
        {"id": name, "kind": "task", "dependencies": [name]}
        for name in ["c", "a", "b"]
    ]
    cycles = build_work_graph(cyclic, source=SOURCE, diagnostic_cap=2)
    assert len(cycles["cycles"]) == 2
    assert cycles["limits"]["cycle_candidates"] == 3
    assert cycles["limits"]["cycles_omitted"] == 1
    assert cycles["projection_state"] == {"state": "partial", "reason": "diagnostics_truncated"}


def test_malformed_relations_are_unresolved_and_function_performs_no_io(monkeypatch):
    records = [
        {
            "id": "a",
            "kind": "task",
            "source_locator": "sealed://run#a",
            "parent_id": 7,
            "allowed_skills": "validate",
            "observed_skills": ["run-log", ""],
            "dependencies": [],
        }
    ]
    records_before = deepcopy(records)
    source_before = deepcopy(SOURCE)

    def fail_open(*args, **kwargs):
        raise AssertionError("projection attempted filesystem I/O")

    monkeypatch.setattr(builtins, "open", fail_open)
    graph = build_work_graph(records, source=SOURCE)

    assert records == records_before
    assert SOURCE == source_before
    reasons = {row["reason"] for row in graph["unresolved"]}
    assert reasons == {"invalid_reference_id", "invalid_relation_list"}
    assert graph["projection_state"] == {"state": "partial", "reason": "unresolved_references"}

    invalid_dependencies = build_work_graph(
        [{"id": "bad-deps", "kind": "task", "dependencies": "not-a-list"}],
        source=SOURCE,
    )
    assert invalid_dependencies["dependency_availability"] == {
        "state": "unavailable",
        "reason": "dependencies_invalid",
    }

    unsupported_identity = build_work_graph(
        [{"id": "\ud800", "kind": "task", "source_locator": "sealed://run#surrogate"}],
        source=SOURCE,
    )
    assert unsupported_identity["nodes"] == []
    assert unsupported_identity["unresolved"] == [
        {
            "reason": "invalid_identity_encoding",
            "record_id": "\ud800",
            "source_locator": "sealed://run#surrogate",
        }
    ]


@pytest.mark.parametrize(
    ("source", "kwargs"),
    [
        ({"namespace": "n", "locator": "l"}, {}),
        ({"namespace": "", "locator": "l", "capture_basis": {"sha256": "x"}}, {}),
        ({"namespace": "\ud800", "locator": "l", "capture_basis": {"sha256": "x"}}, {}),
        (SOURCE, {"record_cap": -1}),
        (SOURCE, {"node_cap": True}),
        (SOURCE, {"diagnostic_cap": 10_001}),
    ],
)
def test_rejects_invalid_source_metadata_and_caps(source, kwargs):
    with pytest.raises((TypeError, ValueError)):
        build_work_graph([], source=source, **kwargs)
