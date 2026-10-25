"""Hostile-input checks for qualification evidence verification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_reharness_qualifications.py"
ZERO = "0" * 64


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True,
                          capture_output=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "user.email", "test@example.test")
    path = root / "skills" / "SKILL.md"
    path.parent.mkdir()
    path.write_text("base\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    base = _git(root, "rev-parse", "HEAD")
    path.write_text("candidate\n")
    _git(root, "commit", "-am", "candidate", "-q")
    return root, base, _git(root, "rev-parse", "HEAD")


def _hash(row):
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _seal(rows):
    previous = ZERO
    for row in rows:
        row["prev_sha256"] = previous
        row.pop("row_sha256", None)
        row["row_sha256"] = _hash(row)
        previous = row["row_sha256"]
    return rows


def _row(repo, commit, name="q"):
    blob = _git(repo, "rev-parse", f"{commit}:skills/SKILL.md")
    return {"schema": "reharness-qualification/v1", "qualification_id": name,
            "prev_sha256": "", "skill_path": "skills/SKILL.md", "skill_commit": commit,
            "skill_blob_sha": blob, "trigger_run_ref": f"run-{name}",
            "applies_when": [{"feature": "score", "op": ">=", "value": 1}],
            "falsified_when": [{"feature": "score", "op": "<", "value": 0}],
            "scope_narrowing": "one local experiment", "row_sha256": ""}


def _run(tmp_path, root, rows):
    ledger = tmp_path / "qualifications.jsonl"
    ledger.write_text("".join(row if isinstance(row, str) else json.dumps(row) + "\n" for row in rows))
    done = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(root), str(ledger)],
                          text=True, capture_output=True, check=False)
    return done, json.loads(done.stdout)


def _invalid(done, report):
    assert done.returncode == 1 and report["valid_count"] == 0
    assert report["qualified_skills"] == [] and report["chain_tip_sha256"] == ZERO
    assert report["errors"]


def test_valid_chain_reports_unique_version_bound_skills(repo, tmp_path):
    root, base, candidate = repo
    rows = _seal([_row(root, base, "one"), _row(root, base, "two"), _row(root, candidate, "three")])
    done, report = _run(tmp_path, root, rows)
    assert done.returncode == 0 and report["valid_count"] == 3 and not report["errors"]
    assert report["chain_tip_sha256"] == rows[-1]["row_sha256"]
    assert [(item["skill_commit"], item["skill_blob_sha"]) for item in report["qualified_skills"]] == sorted([
        (base, _git(root, "rev-parse", f"{base}:skills/SKILL.md")),
        (candidate, _git(root, "rev-parse", f"{candidate}:skills/SKILL.md"))])


def test_broken_previous_and_row_hash_fail_independently(repo, tmp_path):
    root, base, _ = repo
    for change in ("previous", "hash"):
        rows = _seal([_row(root, base)])
        rows[0]["prev_sha256" if change == "previous" else "row_sha256"] = "f" * 64
        _invalid(*_run(tmp_path, root, rows))


def test_tampered_git_blob_fails_closed(repo, tmp_path):
    root, base, _ = repo
    rows = _seal([_row(root, base)])
    rows[0]["skill_blob_sha"] = "0" * 40
    _seal(rows)
    _invalid(*_run(tmp_path, root, rows))


def test_duplicate_json_key_fails_closed(repo, tmp_path):
    root, base, _ = repo
    raw = json.dumps(_seal([_row(root, base)])[0])[:-1] + ',"schema":"reharness-qualification/v1"}'
    _invalid(*_run(tmp_path, root, [raw]))


def test_unknown_missing_and_empty_fields_fail_closed(repo, tmp_path):
    root, base, _ = repo
    for mutate in (lambda row: row.update(extra="no"), lambda row: row.pop("trigger_run_ref"),
                   lambda row: row.update(scope_narrowing="")):
        rows = [_row(root, base)]
        mutate(rows[0])
        _invalid(*_run(tmp_path, root, _seal(rows)))


def test_duplicate_qualification_id_fails_after_resealing(repo, tmp_path):
    root, base, _ = repo
    rows = _seal([_row(root, base, "same"), _row(root, base, "same")])
    _invalid(*_run(tmp_path, root, rows))


def test_predicate_bounds_types_and_bool_value(repo, tmp_path):
    root, base, _ = repo
    good = _seal([_row(root, base)])
    good[0]["applies_when"][0]["value"] = True
    _seal(good)
    assert _run(tmp_path, root, good)[0].returncode == 0
    for value in ([], [{"feature": "x", "op": "?", "value": 1}],
                  [{"feature": "x", "op": "==", "value": "one"}],
                  [{"feature": "x", "op": "==", "value": 1}] * 17):
        rows = [_row(root, base)]
        rows[0]["falsified_when"] = value
        _invalid(*_run(tmp_path, root, _seal(rows)))
    row = _seal([_row(root, base)])[0]
    row["falsified_when"][0]["value"] = float("nan")
    _invalid(*_run(tmp_path, root, [json.dumps(row)]))


def test_empty_malformed_and_missing_git_evidence_fail_closed(repo, tmp_path):
    root, base, _ = repo
    done, report = _run(tmp_path, root, [])
    assert done.returncode == 1 and report["valid_count"] == 0 and not report["errors"]
    _invalid(*_run(tmp_path, root, ["not-json\n"]))
    rows = [_row(root, base)]
    rows[0]["skill_commit"] = "0" * 40
    _invalid(*_run(tmp_path, root, _seal(rows)))
