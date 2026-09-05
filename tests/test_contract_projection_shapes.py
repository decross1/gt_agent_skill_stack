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


@pytest.mark.parametrize("raw", [{"identity": "pass", "review": "pending"}, ["pass"], 7, True])
def test_consumer_contract_preserves_structured_receipt_without_promoting_it(tmp_path, monkeypatch, raw):
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
         "status": "completed", "result": {"done_condition_check": raw}},
    ]
    source.write_text("".join(json.dumps(row) + "\n" for row in rows))
    before = source.read_bytes()
    contracts = ps.build_contracts(consumer, "2026-09-05")
    assert len(contracts) == 1
    assert contracts[0]["status"] == "completed"
    assert contracts[0]["done_check"] == "unverified"
    assert contracts[0]["done_check_raw"] == raw
    assert source.read_bytes() == before


@pytest.mark.parametrize("raw,expected", [
    ("pass", "pass"), (" fail ", "fail"), ("inconclusive", "inconclusive"),
    ("a reported explanation", "freeform"), ("", "unverified"), (None, "unverified"),
])
def test_existing_string_receipts_keep_their_meaning(raw, expected):
    assert ps.normalize_done_check("completed", raw) == expected


def test_spawned_contract_remains_pending_with_structured_receipt():
    assert ps.normalize_done_check("spawned", {"identity": "pass"}) == "pending"
