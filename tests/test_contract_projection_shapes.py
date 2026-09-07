"""Structured consumer check receipts remain evidence, not verdicts."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_summary as ps


@pytest.mark.parametrize("raw", [{"identity": "pass"}, ["pass"], 7, True, {}, [], 0, False])
def test_unsupported_check_shapes_are_unverified(raw):
    assert ps.normalize_done_check("completed", raw) == "unverified"


@pytest.mark.parametrize("raw,expected", [
    ({"identity": "pass", "review": "pending"}, "unverified"),
    (["pass", {"review": "pending"}], "unverified"),
    ({"toString": "not callable", "detail": "<script>&\"'"}, "unverified"),
    (7, "unverified"), (True, "unverified"), ({}, "unverified"),
    ([], "unverified"), (0, "unverified"), (False, "unverified"),
    ("", "unverified"), (None, "unverified"),
    ("pass", "pass"), (" fail ", "fail"), ("inconclusive", "inconclusive"),
    ("a reported explanation", "freeform"),
])
@pytest.mark.parametrize("status", ["completed", "spawned"])
def test_consumer_contract_preserves_receipt_without_promoting_it(tmp_path, monkeypatch, raw, expected, status):
    framework = tmp_path / "framework.jsonl"
    framework.write_text("")
    monkeypatch.setattr(ps, "SPAWN_LEDGER", framework)
    consumer = tmp_path / "consumer"
    (consumer / "run_state").mkdir(parents=True)
    source = consumer / "run_state" / "spawn.jsonl"
    rows = [
        {"spawn_id": "synthetic-check", "timestamp": "2026-09-03T00:00:00Z",
         "status": "spawned", "child_task_id": "synthetic-task", "contract": {}},
        {"spawn_id": "synthetic-check", "timestamp": "2026-09-03T01:00:00Z",
         "status": status, "result": {"done_condition_check": raw}},
    ]
    source.write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = source.read_bytes()
    contracts = ps.build_contracts(consumer, "2026-09-05")
    assert len(contracts) == 1
    assert contracts[0]["status"] == status
    assert contracts[0]["done_check"] == ("pending" if status == "spawned" else expected)
    assert contracts[0]["done_check_raw"] == raw
    assert type(contracts[0]["done_check_raw"]) is type(raw)
    assert source.read_bytes() == before


@pytest.mark.parametrize("raw,expected", [
    ("pass", "pass"), (" fail ", "fail"), ("inconclusive", "inconclusive"),
    ("a reported explanation", "freeform"), ("", "unverified"), (None, "unverified"),
])
def test_existing_string_receipts_keep_their_meaning(raw, expected):
    assert ps.normalize_done_check("completed", raw) == expected


def test_spawned_contract_remains_pending_with_structured_receipt():
    assert ps.normalize_done_check("spawned", {"identity": "pass"}) == "pending"


@pytest.mark.parametrize("status", ["aborted", "escalated", "budget_exceeded"])
def test_terminal_failure_with_reported_pass_is_a_contradiction(
        tmp_path, monkeypatch, status):
    ledger = tmp_path / "spawn.jsonl"
    rows = [
        {
            "spawn_id": "synthetic-contradiction",
            "timestamp": "2026-09-03T00:00:00.123+02:00",
            "status": "spawned",
            "child_task_id": "synthetic-task",
            "contract": {
                "state_basis": "HEAD@deadbeef",
                "skill_subset": ["validate"],
                "authority_cap": "read-only",
                "budget": {
                    "wall_time_seconds": 0,
                    "iterations": 2,
                    "cost_usd": 1.25,
                },
            },
        },
        {
            "spawn_id": "synthetic-contradiction",
            "timestamp": "2026-09-03T00:00:07.999+02:00",
            "status": status,
            "result": {
                "done_condition_check": "pass",
                "verified_by": "parent-task<script>",
                "verified_at": "2026-09-03T00:00:08.001+02:00",
                "child_summary": {"reported": "<child>"},
                "parent_observations": ["wrong <state> basis", "second"],
            },
        },
    ]
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = ledger.read_bytes()
    monkeypatch.setattr(ps, "SPAWN_LEDGER", ledger)

    contract = ps.build_contracts(None, "2026-09-05")[0]

    assert contract["status"] == status
    assert contract["done_check"] == "pass"
    assert contract["done_check_raw"] == "pass"
    assert contract["evaluation_state"] == "contradiction"
    assert contract["started_at"] == rows[0]["timestamp"]
    assert contract["status_at"] == rows[1]["timestamp"]
    assert contract["state_basis"] == "HEAD@deadbeef"
    assert contract["verified_by"] == "parent-task<script>"
    assert contract["verified_at"] == "2026-09-03T00:00:08.001+02:00"
    assert contract["child_summary"] == {"reported": "<child>"}
    assert contract["parent_observations"] == ["wrong <state> basis", "second"]
    assert contract["budget"] == rows[0]["contract"]["budget"]
    assert contract["actual_usage"] is None
    assert ledger.read_bytes() == before


@pytest.mark.parametrize("status,raw,reported,evaluation", [
    (None, "pass", "pass", "unknown"),
    ("unknown-terminal-state", "pass", "pass", "unknown"),
    ("completed", "pass", "pass", "pass"),
    ("spawned", "pass", "pending", "pending"),
    ("completed", {"identity": "pass"}, "unverified", "unknown"),
    ("completed", {}, "unverified", "unknown"),
    ("completed", [], "unverified", "unknown"),
    ("completed", 0, "unverified", "unknown"),
    ("completed", False, "unverified", "unknown"),
])
def test_evaluation_state_requires_a_supported_terminal_check_pair(
        tmp_path, monkeypatch, status, raw, reported, evaluation):
    ledger = tmp_path / "spawn.jsonl"
    first = {
        "spawn_id": "synthetic-state-matrix",
        "timestamp": "2026-09-04T00:00:00Z",
        "status": "spawned",
        "contract": {"budget": {"wall_time_seconds": 45}},
    }
    latest = {
        "spawn_id": "synthetic-state-matrix",
        "timestamp": "2026-09-04T00:00:01Z",
        "result": {"done_condition_check": raw},
    }
    if status is not None:
        latest["status"] = status
    ledger.write_text(json.dumps(first) + "\n" + json.dumps(latest) + "\n")
    before = ledger.read_bytes()
    monkeypatch.setattr(ps, "SPAWN_LEDGER", ledger)

    contract = ps.build_contracts(None, "2026-09-05")[0]

    assert contract["status"] == status
    assert contract["done_check"] == reported
    assert contract["done_check_raw"] == raw
    assert type(contract["done_check_raw"]) is type(raw)
    assert contract["evaluation_state"] == evaluation
    assert contract["verified_by"] is None
    assert contract["verified_at"] is None
    assert contract["child_summary"] is None
    assert contract["parent_observations"] is None
    assert contract["state_basis"] is None
    assert contract["actual_usage"] is None
    assert ledger.read_bytes() == before


@pytest.mark.parametrize("check,expected", [("fail", "fail"), ("inconclusive", "inconclusive")])
def test_completed_execution_does_not_imply_successful_validation(check, expected):
    assert ps.contract_evaluation_state("completed", check) == expected


@pytest.mark.parametrize("spawned_at,completed_at", [
    ("2026-09-05T12:00:00Z", "2026-09-04T12:00:00Z"),
    ("zz-malformed-spawn-time", "aa-malformed-completion-time"),
    ("2026-09-05T12:00:00Z", None),
    (False, "2026-09-04T12:00:00Z"),
    (0, {"reported": "unparseable"}),
    ([], "2026-09-04T12:00:00Z"),
    ({"source": "clock"}, ""),
])
def test_contract_lineage_follows_physical_ledger_order(
        tmp_path, monkeypatch, spawned_at, completed_at):
    ledger = tmp_path / "spawn.jsonl"
    rows = [
        {
            "spawn_id": "synthetic-append-order",
            "timestamp": spawned_at,
            "status": "spawned",
            "child_task_id": "physical-first-task",
            "contract": {
                "state_basis": "HEAD@physical-first",
                "skill_subset": ["validate"],
                "authority_cap": "bounded",
                "budget": {"wall_time_seconds": 0},
            },
        },
        {
            "spawn_id": "synthetic-append-order",
            "timestamp": completed_at,
            "status": "completed",
            "child_task_id": "must-not-replace-first",
            "contract": {"state_basis": "HEAD@must-not-replace-first"},
            "result": {
                "done_condition_check": False,
                "verified_by": "physical-latest-evaluator",
                "verified_at": "reported-verification-time",
                "child_summary": {"reported": False},
                "parent_observations": [],
            },
        },
    ]
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = ledger.read_bytes()
    monkeypatch.setattr(ps, "SPAWN_LEDGER", ledger)

    contract = ps.build_contracts(None, "2026-09-05")[0]

    assert contract["status"] == "completed"
    assert contract["started_at"] == spawned_at
    assert contract["status_at"] == completed_at
    assert contract["task"] == "physical-first-task"
    assert contract["state_basis"] == "HEAD@physical-first"
    assert contract["budget"] == {"wall_time_seconds": 0}
    assert contract["done_check_raw"] is False
    assert contract["done_check"] == "unverified"
    assert contract["evaluation_state"] == "unknown"
    assert contract["verified_by"] == "physical-latest-evaluator"
    assert contract["verified_at"] == "reported-verification-time"
    assert contract["child_summary"] == {"reported": False}
    assert contract["parent_observations"] == []
    assert ledger.read_bytes() == before


def test_identical_spawn_ids_remain_distinct_across_source_ledgers(
        tmp_path, monkeypatch):
    framework = tmp_path / "framework.jsonl"
    framework_rows = [
        {
            "spawn_id": "synthetic-shared-id",
            "timestamp": "framework-malformed-start",
            "status": "spawned",
            "child_task_id": "framework-task",
            "contract": {"state_basis": "HEAD@framework"},
        },
        {
            "spawn_id": "synthetic-shared-id",
            "timestamp": "1900-01-01T00:00:00Z",
            "status": "completed",
            "result": {"done_condition_check": "fail"},
        },
    ]
    framework.write_text("".join(json.dumps(row) + "\n" for row in framework_rows))
    consumer = tmp_path / "consumer"
    (consumer / "run_state").mkdir(parents=True)
    apparatus = consumer / "run_state" / "spawn.jsonl"
    apparatus_rows = [
        {
            "spawn_id": "synthetic-shared-id",
            "timestamp": "apparatus-malformed-start",
            "status": "spawned",
            "child_task_id": "apparatus-task",
            "contract": {"state_basis": "snapshot:apparatus"},
        },
        {
            "spawn_id": "synthetic-shared-id",
            "timestamp": "1800-01-01T00:00:00Z",
            "status": "completed",
            "result": {"done_condition_check": "pass"},
        },
    ]
    apparatus.write_text("".join(json.dumps(row) + "\n" for row in apparatus_rows))
    framework_before = framework.read_bytes()
    apparatus_before = apparatus.read_bytes()
    monkeypatch.setattr(ps, "SPAWN_LEDGER", framework)

    contracts = ps.build_contracts(consumer, "2026-09-05")

    assert len(contracts) == 2
    by_surface = {contract["surface"]: contract for contract in contracts}
    assert set(by_surface) == {"framework", "apparatus"}
    assert {contract["spawn_id"] for contract in contracts} == {"synthetic-shared-id"}
    assert by_surface["framework"]["task"] == "framework-task"
    assert by_surface["framework"]["state_basis"] == "HEAD@framework"
    assert by_surface["framework"]["started_at"] == "framework-malformed-start"
    assert by_surface["framework"]["status_at"] == "1900-01-01T00:00:00Z"
    assert by_surface["framework"]["done_check_raw"] == "fail"
    assert by_surface["apparatus"]["task"] == "apparatus-task"
    assert by_surface["apparatus"]["state_basis"] == "snapshot:apparatus"
    assert by_surface["apparatus"]["started_at"] == "apparatus-malformed-start"
    assert by_surface["apparatus"]["status_at"] == "1800-01-01T00:00:00Z"
    assert by_surface["apparatus"]["done_check_raw"] == "pass"
    assert framework.read_bytes() == framework_before
    assert apparatus.read_bytes() == apparatus_before
