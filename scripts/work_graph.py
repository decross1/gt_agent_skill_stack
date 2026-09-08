"""Pure, bounded projection of caller-supplied work records.

The projector deliberately knows nothing about repository layout, clocks,
processes, authentication, or agent liveness.  Every identity and relation in
the result comes from an explicit input field.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
from typing import Any
from urllib.parse import quote


SCHEMA_VERSION = "work-graph/v1"
DEFAULT_RECORD_CAP = 2_048
DEFAULT_NODE_CAP = 256
DEFAULT_EDGE_CAP = 1_024
DEFAULT_DIAGNOSTIC_CAP = 256

_MAX_RECORD_CAP = 10_000
_MAX_NODE_CAP = 10_000
_MAX_EDGE_CAP = 50_000
_MAX_DIAGNOSTIC_CAP = 10_000

_LIST_RELATIONS = {
    "spawn_assignments": "spawn_assignment",
    "allowed_skills": "allowed_skill",
    "observed_skills": "observed_skill",
    "dependencies": "dependency",
}


def _validate_cap(name: str, value: int, maximum: int) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer item count")
    if value < 0 or value > maximum:
        raise ValueError(f"{name} must be between 0 and {maximum}")


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _encoded(value: str) -> str:
    return quote(value, safe="")


def _supports_utf8(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _dependency_field_state(record: Mapping[str, Any]) -> str:
    """Classify supplied dependency evidence before identity validation."""

    if "dependencies" not in record:
        return "absent"
    values = record["dependencies"]
    if not isinstance(values, list):
        return "invalid"
    if any(
        not isinstance(target_id, str)
        or not target_id
        or not _supports_utf8(target_id)
        for target_id in values
    ):
        return "invalid"
    return "valid"


def _work_id(namespace: str, kind: str, record_id: str) -> str:
    return f"work:{_encoded(namespace)}:{_encoded(kind)}:{_encoded(record_id)}"


def _skill_id(namespace: str, skill_id: str) -> str:
    return f"skill:{_encoded(namespace)}:{_encoded(skill_id)}"


def _edge_id(edge_type: str, source_id: str, target_id: str) -> str:
    return f"edge:{_encoded(edge_type)}:{_encoded(source_id)}:{_encoded(target_id)}"


def _record_locator(record: Mapping[str, Any], source: Mapping[str, Any]) -> Any:
    locator = record.get("source_locator")
    if isinstance(locator, str) and locator and _supports_utf8(locator):
        return locator
    return {
        "collection": source["locator"],
        "record": {"kind": record.get("kind"), "id": record.get("id")},
    }


def _empty_limits(
    *,
    record_count: int,
    record_cap: int,
    node_cap: int,
    edge_cap: int,
    diagnostic_cap: int,
) -> dict[str, Any]:
    return {
        "unit": "items",
        "record_cap": record_cap,
        "record_count": record_count,
        "node_cap": node_cap,
        "edge_cap": edge_cap,
        "diagnostic_cap": diagnostic_cap,
        "node_candidates": 0,
        "edge_candidates": 0,
        "unresolved_candidates": 0,
        "cycle_candidates": 0,
        "nodes_omitted": 0,
        "edges_omitted": 0,
        "unresolved_omitted": 0,
        "cycles_omitted": 0,
    }


def _base_result(source: Mapping[str, Any], limits: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": deepcopy(dict(source)),
        "projection_state": {"state": "complete", "reason": None},
        "dependency_availability": {"state": "unavailable", "reason": "dependencies_not_supplied"},
        "limits": limits,
        "nodes": [],
        "edges": [],
        "unresolved": [],
        "cycles": [],
    }


def _dependency_cycles(node_ids: Sequence[str], edges: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return canonical strongly connected components for dependency edges."""

    adjacency = {node_id: set() for node_id in node_ids}
    reverse = {node_id: set() for node_id in node_ids}
    for edge in edges:
        if edge["type"] != "dependency":
            continue
        adjacency[edge["source"]].add(edge["target"])
        reverse[edge["target"]].add(edge["source"])

    ordered_adjacency = {node_id: sorted(targets) for node_id, targets in adjacency.items()}
    ordered_reverse = {node_id: sorted(targets) for node_id, targets in reverse.items()}
    visited: set[str] = set()
    finish_order: list[str] = []

    for start in sorted(node_ids):
        if start in visited:
            continue
        visited.add(start)
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            node_id, offset = stack[-1]
            neighbors = ordered_adjacency[node_id]
            if offset < len(neighbors):
                neighbor = neighbors[offset]
                stack[-1] = (node_id, offset + 1)
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append((neighbor, 0))
                continue
            stack.pop()
            finish_order.append(node_id)

    assigned: set[str] = set()
    cycles: list[dict[str, Any]] = []
    for start in reversed(finish_order):
        if start in assigned:
            continue
        component: list[str] = []
        assigned.add(start)
        stack = [start]
        while stack:
            node_id = stack.pop()
            component.append(node_id)
            for neighbor in reversed(ordered_reverse[node_id]):
                if neighbor not in assigned:
                    assigned.add(neighbor)
                    stack.append(neighbor)
        component.sort()
        if len(component) > 1 or component[0] in adjacency[component[0]]:
            cycles.append({"type": "dependency", "node_ids": component})

    return sorted(cycles, key=_canonical)


def build_work_graph(
    records: Sequence[Mapping[str, Any]],
    *,
    source: Mapping[str, Any],
    record_cap: int = DEFAULT_RECORD_CAP,
    node_cap: int = DEFAULT_NODE_CAP,
    edge_cap: int = DEFAULT_EDGE_CAP,
    diagnostic_cap: int = DEFAULT_DIAGNOSTIC_CAP,
) -> dict[str, Any]:
    """Project explicit work records into a stable, count-bounded graph.

    ``source`` must contain non-empty ``namespace`` and ``locator`` strings and
    a non-empty mapping named ``capture_basis``.  Caps count returned or
    supplied items; they do not claim to bound serialized bytes.

    The function performs no I/O and does not mutate ``records`` or ``source``.
    An input larger than ``record_cap`` returns an unavailable, fail-closed
    projection without inspecting individual records.
    """

    if not isinstance(source, Mapping):
        raise TypeError("source must be a mapping")
    namespace = source.get("namespace")
    locator = source.get("locator")
    capture_basis = source.get("capture_basis")
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("source.namespace must be a non-empty exact string")
    if not isinstance(locator, str) or not locator:
        raise ValueError("source.locator must be a non-empty exact string")
    if not _supports_utf8(namespace) or not _supports_utf8(locator):
        raise ValueError("source namespace and locator must contain UTF-8 scalar strings")
    if not isinstance(capture_basis, Mapping) or not capture_basis:
        raise ValueError("source.capture_basis must be a non-empty mapping")
    if isinstance(records, (str, bytes, bytearray)) or not isinstance(records, Sequence):
        raise TypeError("records must be a finite sequence of mappings")

    _validate_cap("record_cap", record_cap, _MAX_RECORD_CAP)
    _validate_cap("node_cap", node_cap, _MAX_NODE_CAP)
    _validate_cap("edge_cap", edge_cap, _MAX_EDGE_CAP)
    _validate_cap("diagnostic_cap", diagnostic_cap, _MAX_DIAGNOSTIC_CAP)

    record_count = len(records)
    limits = _empty_limits(
        record_count=record_count,
        record_cap=record_cap,
        node_cap=node_cap,
        edge_cap=edge_cap,
        diagnostic_cap=diagnostic_cap,
    )
    result = _base_result(source, limits)

    if record_count > record_cap:
        issue = {
            "reason": "record_cap_exceeded",
            "record_count": record_count,
            "record_cap": record_cap,
            "source_locator": locator,
        }
        limits["unresolved_candidates"] = 1
        if diagnostic_cap:
            result["unresolved"] = [issue]
        else:
            limits["unresolved_omitted"] = 1
        result["projection_state"] = {"state": "unavailable", "reason": "record_cap_exceeded"}
        result["dependency_availability"] = {
            "state": "unavailable",
            "reason": "projection_unavailable",
        }
        return result

    unresolved: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    dependency_mapping_records = 0
    dependency_absent = 0
    dependency_valid = 0
    dependency_invalid = 0

    for supplied_record in records:
        if not isinstance(supplied_record, Mapping):
            unresolved.append({"reason": "invalid_record", "source_locator": locator})
            continue
        record = deepcopy(dict(supplied_record))
        dependency_mapping_records += 1
        dependency_state = _dependency_field_state(record)
        if dependency_state == "absent":
            dependency_absent += 1
        elif dependency_state == "valid":
            dependency_valid += 1
        else:
            dependency_invalid += 1
        try:
            canonical = _canonical(record)
        except (TypeError, ValueError):
            unresolved.append({"reason": "invalid_record", "source_locator": locator})
            continue

        record_id = record.get("id")
        kind = record.get("kind")
        source_locator = _record_locator(record, source)
        if not isinstance(record_id, str) or not record_id:
            unresolved.append({"reason": "missing_id", "source_locator": source_locator})
            continue
        if not isinstance(kind, str) or not kind:
            unresolved.append(
                {"reason": "missing_kind", "record_id": record_id, "source_locator": source_locator}
            )
            continue
        if not _supports_utf8(record_id) or not _supports_utf8(kind):
            unresolved.append(
                {
                    "reason": "invalid_identity_encoding",
                    "record_id": record_id,
                    "source_locator": source_locator,
                }
            )
            continue
        if "source_locator" in record and (
            not isinstance(record["source_locator"], str)
            or not record["source_locator"]
            or not _supports_utf8(record["source_locator"])
        ):
            unresolved.append(
                {
                    "reason": "invalid_source_locator",
                    "record_id": record_id,
                    "source_locator": source_locator,
                }
            )
        grouped.setdefault(record_id, []).append(
            {
                "record": record,
                "canonical": canonical,
                "source_locator": source_locator,
                "dependency_state": dependency_state,
            }
        )

    valid: dict[str, dict[str, Any]] = {}
    ambiguous_ids: set[str] = set()
    for record_id in sorted(grouped):
        entries = grouped[record_id]
        if len(entries) == 1:
            valid[record_id] = entries[0]["record"]
            continue
        ambiguous_ids.add(record_id)
        variants = {entry["canonical"] for entry in entries}
        reason = "duplicate_id" if len(variants) == 1 else "conflicting_id"
        source_locators = sorted(
            (deepcopy(entry["source_locator"]) for entry in entries), key=_canonical
        )
        unresolved.append(
            {
                "reason": reason,
                "record_id": record_id,
                "occurrences": len(entries),
                "source_locators": source_locators,
            }
        )

    dependency_projectable = sum(
        1
        for record_id in valid
        if grouped[record_id][0]["dependency_state"] == "valid"
    )
    node_candidates: dict[str, tuple[int, dict[str, Any]]] = {}
    edge_candidates: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_issue(
        *,
        reason: str,
        relation: str,
        record_id: str,
        source_locator: Any,
        target_id: Any | None = None,
    ) -> None:
        issue = {
            "reason": reason,
            "relation": relation,
            "record_id": record_id,
            "source_locator": deepcopy(source_locator),
        }
        if target_id is not None:
            issue["target_id"] = target_id
        unresolved.append(issue)

    def resolve_work_target(
        *,
        relation: str,
        record_id: str,
        target_id: str,
        source_locator: Any,
    ) -> str | None:
        if target_id in valid:
            target = valid[target_id]
            return _work_id(namespace, target["kind"], target_id)
        reason = "ambiguous_target_id" if target_id in ambiguous_ids else "missing_target_id"
        add_issue(
            reason=reason,
            relation=relation,
            record_id=record_id,
            target_id=target_id,
            source_locator=source_locator,
        )
        return None

    def add_edge(edge_type: str, source_id: str, target_id: str, source_locator: Any) -> None:
        key = (edge_type, source_id, target_id)
        edge = {
            "id": _edge_id(edge_type, source_id, target_id),
            "type": edge_type,
            "source": source_id,
            "target": target_id,
            "source_locator": deepcopy(source_locator),
            "source_metadata": deepcopy(dict(source)),
        }
        if edge_type == "observed_skill":
            edge["assertion_basis"] = "caller_supplied"
        previous = edge_candidates.get(key)
        if previous is None or _canonical(edge["source_locator"]) < _canonical(
            previous["source_locator"]
        ):
            edge_candidates[key] = edge

    for record_id in sorted(valid):
        record = valid[record_id]
        kind = record["kind"]
        node_id = _work_id(namespace, kind, record_id)
        source_locator = _record_locator(record, source)
        node = {
            "id": node_id,
            "type": "work",
            "record_id": record_id,
            "kind": kind,
            "source_locator": deepcopy(source_locator),
            "source_metadata": deepcopy(dict(source)),
        }
        if "role" in record:
            node["role"] = deepcopy(record["role"])
        if "raw_status" in record:
            node["raw_status"] = deepcopy(record["raw_status"])
        node_candidates[node_id] = (0, node)

        if "parent_id" in record:
            parent_id = record["parent_id"]
            if not isinstance(parent_id, str) or not parent_id:
                add_issue(
                    reason="invalid_reference_id",
                    relation="parent",
                    record_id=record_id,
                    source_locator=source_locator,
                )
            elif not _supports_utf8(parent_id):
                add_issue(
                    reason="invalid_identity_encoding",
                    relation="parent",
                    record_id=record_id,
                    target_id=parent_id,
                    source_locator=source_locator,
                )
            else:
                parent_node_id = resolve_work_target(
                    relation="parent",
                    record_id=record_id,
                    target_id=parent_id,
                    source_locator=source_locator,
                )
                if parent_node_id is not None:
                    add_edge("parent", parent_node_id, node_id, source_locator)

        for field, relation in _LIST_RELATIONS.items():
            if field not in record:
                continue
            values = record[field]
            if not isinstance(values, list):
                add_issue(
                    reason="invalid_relation_list",
                    relation=relation,
                    record_id=record_id,
                    source_locator=source_locator,
                )
                continue
            valid_values: set[str] = set()
            for target_id in values:
                if not isinstance(target_id, str) or not target_id:
                    add_issue(
                        reason="invalid_reference_id",
                        relation=relation,
                        record_id=record_id,
                        source_locator=source_locator,
                    )
                    continue
                if not _supports_utf8(target_id):
                    add_issue(
                        reason="invalid_identity_encoding",
                        relation=relation,
                        record_id=record_id,
                        target_id=target_id,
                        source_locator=source_locator,
                    )
                    continue
                valid_values.add(target_id)
            for target_id in sorted(valid_values):
                if relation in {"allowed_skill", "observed_skill"}:
                    target_node_id = _skill_id(namespace, target_id)
                    node_candidates.setdefault(
                        target_node_id,
                        (
                            1,
                            {
                                "id": target_node_id,
                                "type": "skill",
                                "skill_id": target_id,
                                "source_locator": {
                                    "collection": locator,
                                    "skill_id": target_id,
                                },
                                "source_metadata": deepcopy(dict(source)),
                            },
                        ),
                    )
                else:
                    target_node_id = resolve_work_target(
                        relation=relation,
                        record_id=record_id,
                        target_id=target_id,
                        source_locator=source_locator,
                    )
                    if target_node_id is None:
                        continue
                add_edge(relation, node_id, target_node_id, source_locator)

    dependency_supplied = dependency_valid + dependency_invalid
    if dependency_supplied == 0:
        result["dependency_availability"] = {
            "state": "unavailable",
            "reason": "dependencies_not_supplied",
        }
    elif dependency_valid == 0:
        result["dependency_availability"] = {
            "state": "unavailable",
            "reason": "dependencies_invalid",
        }
    elif dependency_projectable == 0:
        result["dependency_availability"] = {
            "state": "unavailable",
            "reason": "dependencies_identity_unresolved",
        }
    elif (
        dependency_valid == dependency_mapping_records
        and dependency_projectable == dependency_valid
        and dependency_absent == 0
        and dependency_invalid == 0
    ):
        result["dependency_availability"] = {"state": "available", "reason": None}
    else:
        result["dependency_availability"] = {
            "state": "partial",
            "reason": "dependencies_partially_available",
        }

    ordered_nodes = [
        item[1] for item in sorted(node_candidates.values(), key=lambda item: (item[0], item[1]["id"]))
    ]
    ordered_edges = sorted(edge_candidates.values(), key=lambda edge: edge["id"])
    selected_nodes = ordered_nodes[:node_cap]
    selected_node_ids = {node["id"] for node in selected_nodes}
    selectable_edges = [
        edge
        for edge in ordered_edges
        if edge["source"] in selected_node_ids and edge["target"] in selected_node_ids
    ]
    selected_edges = selectable_edges[:edge_cap]

    work_node_ids = [
        candidate[1]["id"] for candidate in node_candidates.values() if candidate[1]["type"] == "work"
    ]
    cycles = _dependency_cycles(work_node_ids, ordered_edges)
    ordered_unresolved = sorted(unresolved, key=_canonical)

    limits["node_candidates"] = len(ordered_nodes)
    limits["edge_candidates"] = len(ordered_edges)
    limits["unresolved_candidates"] = len(ordered_unresolved)
    limits["cycle_candidates"] = len(cycles)
    limits["nodes_omitted"] = len(ordered_nodes) - len(selected_nodes)
    limits["edges_omitted"] = len(ordered_edges) - len(selected_edges)
    limits["unresolved_omitted"] = max(0, len(ordered_unresolved) - diagnostic_cap)
    limits["cycles_omitted"] = max(0, len(cycles) - diagnostic_cap)

    result["nodes"] = selected_nodes
    result["edges"] = selected_edges
    result["unresolved"] = ordered_unresolved[:diagnostic_cap]
    result["cycles"] = cycles[:diagnostic_cap]

    if limits["unresolved_omitted"] or limits["cycles_omitted"]:
        result["projection_state"] = {"state": "partial", "reason": "diagnostics_truncated"}
    elif limits["nodes_omitted"] or limits["edges_omitted"]:
        result["projection_state"] = {"state": "partial", "reason": "projection_truncated"}
    elif ordered_unresolved:
        result["projection_state"] = {"state": "partial", "reason": "unresolved_references"}

    return result
