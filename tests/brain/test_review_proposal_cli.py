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
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REAL_CLI = REPO / "scripts" / "review_proposal_cli.py"
REAL_LEDGER_HELPER = REPO / "scripts" / "brain_ledger.py"
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
    shutil.copy(REAL_LEDGER_HELPER, fake_scripts / "brain_ledger.py")
    ledger = tmp_path / "memory" / "brain" / "proposals.jsonl"
    ledger.parent.mkdir(parents=True)

    real_before = REAL_LEDGER.read_bytes() if REAL_LEDGER.exists() else None

    def run(*args, seed=None, actor="derrick"):
        if seed is not None:
            ledger.write_text("".join(json.dumps(r) + "\n" for r in seed))
        actor_args = ["--actor", actor] if actor is not None else []
        proc = subprocess.run(
            [sys.executable, str(fake_scripts / "review_proposal_cli.py"), *args, *actor_args],
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


def test_missing_note_on_reject_exits_5(cli_env):
    # A reject owes a reason (review-proposal: "a rejection without a reason is
    # an opinion"); whitespace-only note is treated as missing.
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "reject",
               "--note", "   ", seed=[OPEN_ROW])
    assert proc.returncode == 5
    assert len(_outcome_lines(ledger)) == 1  # nothing appended


def test_missing_note_on_reject_default_empty_exits_5(cli_env):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "reject", seed=[OPEN_ROW])
    assert proc.returncode == 5
    assert len(_outcome_lines(ledger)) == 1


def test_accept_without_note_succeeds(cli_env):
    # Accept is the human-authority path — a reason is optional. Empty note is OK
    # and records an accepted outcome with an empty verdict_reasoning.
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept", seed=[OPEN_ROW])
    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["ok"] is True
    assert payload["recorded"] == "accepted"
    assert payload["proposal_id"] == "P-901"
    rows = _outcome_lines(ledger)
    assert len(rows) == 2
    assert rows[-1]["verdict"] == "accepted"
    assert rows[-1]["verdict_reasoning"] == ""
    assert rows[-1]["decision_schema_version"] == "proposal-verdict-v2"
    assert rows[-1]["accepted_body_schema"] == "proposal-change-v1"
    assert rows[-1]["accepted_body"] == OPEN_ROW["change"]
    assert rows[-1]["accepted_body_sha256"] == hashlib.sha256(
        OPEN_ROW["change"].encode("utf-8")).hexdigest()


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
    assert payload["ok"] is True
    assert payload["recorded"] == recorded
    assert payload["proposal_id"] == "P-901"

    rows = _outcome_lines(ledger)
    assert len(rows) == 2  # exactly one appended
    out = rows[-1]
    assert out["proposal_id"] == "P-901"
    assert out["verdict"] == recorded
    assert out["agent_id"] == "derrick"
    assert out["actor"] == {
        "id": "derrick", "type": "human", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    }
    assert out["status"] == "closed"
    assert out["supersedes_proposal_id"] == "P-901"
    assert out["verdict_reasoning"] == "considered reasoning"
    assert "timestamp" in out and out["timestamp"]
    if recorded == "rejected":
        assert "accepted_body" not in out
        assert "accepted_body_sha256" not in out


def test_explicit_actor_persists_exact_derrick_attribution(cli_env):
    run, ledger = cli_env
    run("--proposal-id", "P-901", "--verdict", "accept",
        "--note", "ok", seed=[OPEN_ROW])
    out = _outcome_lines(ledger)[-1]
    assert out["agent_id"] == "derrick"
    assert out["actor"] == {
        "id": "derrick", "type": "human", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    }


def test_explicit_actor_persists_exact_oracle_attribution(cli_env):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept",
               "--note", "recorded by Oracle", seed=[OPEN_ROW], actor="oracle")
    assert proc.returncode == 0
    out = _outcome_lines(ledger)[-1]
    assert out["agent_id"] == "oracle"
    assert out["actor"] == {
        "id": "oracle", "type": "agent", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    }


@pytest.mark.parametrize("actor", [None, "mallory", "human:ui"])
def test_missing_or_unknown_actor_exits_2_and_writes_nothing(cli_env, actor):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept", "--note", "x",
               seed=[OPEN_ROW], actor=actor)
    assert proc.returncode == 2
    assert len(_outcome_lines(ledger)) == 1


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


# ---------------------------------------------------------------------------
# --basis {original,amended} — recorded on the outcome (new contract §3)
# ---------------------------------------------------------------------------

def test_basis_defaults_to_original(cli_env):
    """No --basis flag -> the appended outcome records basis 'original'."""
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept",
               "--note", "ship the original", seed=[OPEN_ROW])
    assert proc.returncode == 0
    assert _outcome_lines(ledger)[-1]["basis"] == "original"


def test_basis_amended_is_recorded(cli_env):
    """--basis amended -> the appended outcome carries basis 'amended', while the
    rest of the well-formed outcome (verdict, actor, status) is unchanged."""
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept",
               "--note", "ship the amended draft", "--basis", "amended",
               "--accepted-body", "exact amended proposal",
               seed=[OPEN_ROW])
    assert proc.returncode == 0
    out = _outcome_lines(ledger)[-1]
    assert out["basis"] == "amended"
    assert out["verdict"] == "accepted"
    assert out["agent_id"] == "derrick"
    assert out["status"] == "closed"
    assert out["accepted_body"] == "exact amended proposal"
    assert out["accepted_body_sha256"] == hashlib.sha256(
        b"exact amended proposal").hexdigest()


def test_amended_accept_requires_exact_body_and_writes_nothing_without_it(cli_env):
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept", "--basis", "amended",
               "--note", "x", seed=[OPEN_ROW])
    assert proc.returncode == 2
    assert len(_outcome_lines(ledger)) == 1


def test_oversized_amended_body_is_refused_before_ledger_append(cli_env):
    run, ledger = cli_env
    oversized = "x" * (64 * 1024 + 1)
    proc = run("--proposal-id", "P-901", "--verdict", "accept", "--basis", "amended",
               "--accepted-body", oversized, "--note", "x", seed=[OPEN_ROW])
    assert proc.returncode == 2
    assert len(_outcome_lines(ledger)) == 1


def test_original_accept_with_unreconstructible_filing_refuses_without_append(cli_env):
    run, ledger = cli_env
    broken = dict(OPEN_ROW)
    broken.pop("change")
    proc = run("--proposal-id", "P-901", "--verdict", "accept", "--note", "x",
               seed=[broken])
    assert proc.returncode == 7
    assert _outcome_lines(ledger) == [broken]


def test_basis_original_explicit_is_recorded(cli_env):
    """--basis original (explicit) records basis 'original'."""
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "reject",
               "--note", "no thanks", "--basis", "original", seed=[OPEN_ROW])
    assert proc.returncode == 0
    out = _outcome_lines(ledger)[-1]
    assert out["basis"] == "original"
    assert out["verdict"] == "rejected"


def test_bad_basis_rejected_and_writes_nothing(cli_env):
    """--basis is a frozen enum; an out-of-enum value is refused by argparse
    (exit 2) and nothing is appended to the ledger."""
    run, ledger = cli_env
    proc = run("--proposal-id", "P-901", "--verdict", "accept",
               "--note", "x", "--basis", "fabricated", seed=[OPEN_ROW])
    assert proc.returncode != 0
    assert len(_outcome_lines(ledger)) == 1  # only the seeded row remains
