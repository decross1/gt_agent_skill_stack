#!/usr/bin/env python3
"""Tests for scripts/review_proposal_cli.py — the blessed human-verdict CLI.

The CLI derives its ledger path from `ROOT = Path(__file__).resolve().parent.parent`
(no env / argv override), so to drive it against a TEMP ledger without ever
touching the real one we reconstruct a minimal fake ROOT in tmp_path:

    <tmp>/scripts/review_proposal_cli.py   (a copy of the real CLI)
    <tmp>/memory/brain/proposals.jsonl     (a temp ledger seeded per-test)

Running the *copy* makes the CLI's PROPOSALS point at the temp ledger. The real
memory/brain/proposals.jsonl is never read or written by these tests.

Exit-code contract under test (from the CLI's own docstring):
  0 ok · 2 bad proposal_id · 3 unknown proposal · 4 already decided
  · 5 missing note · 6 io error.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REAL_CLI = REPO / "scripts" / "review_proposal_cli.py"
REAL_LEDGER = REPO / "memory" / "brain" / "proposals.jsonl"

OPEN_ROW = {
    "timestamp": "2026-05-24T19:00:00Z",
    "proposal_id": "P-901",
    "agent_id": "claude-code-main",
    "title": "A framework proposal under test",
    "target_type": "skill",
    "target": "validate",
    "change": "tighten the validate skill",
    "reasoning": "because",
    "status": "open",
}


@pytest.fixture
def cli_env(tmp_path):
    """Build a fake ROOT so the copied CLI writes to a TEMP ledger.

    Returns (run, ledger) where `run(*args)` invokes the copied CLI and
    `ledger` is the temp proposals.jsonl Path. The real ledger is captured
    before and asserted unchanged after, so a stray write to it fails the test.
    """
    fake_scripts = tmp_path / "scripts"
    fake_scripts.mkdir()
    shutil.copy(REAL_CLI, fake_scripts / "review_proposal_cli.py")
    ledger = tmp_path / "memory" / "brain" / "proposals.jsonl"
    ledger.parent.mkdir(parents=True)

    real_before = REAL_LEDGER.read_bytes() if REAL_LEDGER.exists() else None

    def run(*args, seed=None):
        if seed is not None:
            ledger.write_text("".join(json.dumps(r) + "\n" for r in seed))
        proc = subprocess.run(
            [sys.executable, str(fake_scripts / "review_proposal_cli.py"), *args],
            capture_output=True, text=True, timeout=30,
        )
        return proc

    yield run, ledger

    # Guard: the real canonical ledger must be byte-identical to before.
    real_after = REAL_LEDGER.read_bytes() if REAL_LEDGER.exists() else None
    assert real_after == real_before, "real proposals.jsonl was mutated by a test"


def _outcome_lines(ledger: Path) -> list[dict]:
    return [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]


# ---------------------------------------------------------------------------
# Bad / rejected input — must exit nonzero and write nothing
# ---------------------------------------------------------------------------

def test_bad_proposal_id_exits_2_and_writes_nothing(cli_env):
    run, ledger = cli_env
    proc = run("--proposal-id", "not-a-pid", "--verdict", "accept",
               "--note", "x", seed=[OPEN_ROW])
    assert proc.returncode == 2
    # Exactly the one seeded row remains — no outcome appended.
    rows = _outcome_lines(ledger)
    assert len(rows) == 1 and rows[0]["proposal_id"] == "P-901"
    assert rows[0].get("verdict") is None


def test_unknown_proposal_exits_3(cli_env):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-404", "--verdict", "accept",
               "--note", "x", seed=[OPEN_ROW])
    assert proc.returncode == 3
    assert len(_outcome_lines(ledger)) == 1  # nothing appended


def test_missing_note_exits_5(cli_env):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept",
               "--note", "   ", seed=[OPEN_ROW])
    assert proc.returncode == 5
    assert len(_outcome_lines(ledger)) == 1  # nothing appended


def test_missing_note_default_empty_exits_5(cli_env):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept", seed=[OPEN_ROW])
    assert proc.returncode == 5
    assert len(_outcome_lines(ledger)) == 1


# ---------------------------------------------------------------------------
# Valid verdicts — exactly one well-formed outcome line
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("arg,recorded", [("accept", "accepted"),
                                          ("reject", "rejected")])
def test_valid_verdict_appends_one_wellformed_outcome(cli_env, arg, recorded):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", arg,
               "--note", "considered reasoning", seed=[OPEN_ROW])
    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload == {"ok": True, "recorded": recorded, "proposal_id": "P-901"}

    rows = _outcome_lines(ledger)
    assert len(rows) == 2  # exactly one appended
    out = rows[-1]
    assert out["proposal_id"] == "P-901"
    assert out["verdict"] == recorded
    assert out["agent_id"] == "human:ui"
    assert out["status"] == "closed"
    assert out["supersedes_proposal_id"] == "P-901"
    assert out["verdict_reasoning"] == "considered reasoning"
    assert "timestamp" in out and out["timestamp"]


def test_default_agent_is_human_ui(cli_env):
    run, ledger = cli_env
    run("--proposal-id", "P-901", "--verdict", "accept",
        "--note", "ok", seed=[OPEN_ROW])
    assert _outcome_lines(ledger)[-1]["agent_id"] == "human:ui"


# ---------------------------------------------------------------------------
# Already decided — second verdict refused
# ---------------------------------------------------------------------------

def test_second_verdict_on_decided_proposal_exits_4(cli_env):
    run, ledger = cli_env
    first = run("--proposal-id", "P-901", "--verdict", "accept",
                "--note", "first", seed=[OPEN_ROW])
    assert first.returncode == 0
    assert len(_outcome_lines(ledger)) == 2

    second = run("--proposal-id", "P-901", "--verdict", "reject", "--note", "second")
    assert second.returncode == 4
    # No further append — still exactly two rows.
    assert len(_outcome_lines(ledger)) == 2


def test_needs_revision_stays_reopenable(cli_env):
    """needs_revision records 'human-review' (status human-review, not closed),
    which leaves the proposal decidable again — a follow-up accept succeeds."""
    run, ledger = cli_env
    rev = run("--proposal-id", "P-901", "--verdict", "needs_revision",
              "--note", "needs work", seed=[OPEN_ROW])
    assert rev.returncode == 0
    rev_row = _outcome_lines(ledger)[-1]
    assert rev_row["verdict"] == "human-review"
    assert rev_row["status"] == "human-review"

    follow = run("--proposal-id", "P-901", "--verdict", "accept", "--note", "now ok")
    assert follow.returncode == 0
    assert _outcome_lines(ledger)[-1]["verdict"] == "accepted"
