"""End-to-end hostile-input checks for the skill-lift receipt verifier."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_skill_lift.py"


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


def _row(repo, base, candidate, task, arm, passed):
    commit = base if arm == "base" else candidate
    blob = _git(repo, "rev-parse", f"{commit}:skills/SKILL.md")
    return {"schema": "skill-lift-run/v1", "task_id": task, "arm": arm,
            "skill_path": "skills/SKILL.md", "skill_commit": commit,
            "skill_blob_sha": blob, "task_set_sha256": "a" * 64,
            "passed": passed, "run_ref": f"run-{task}-{arm}"}


def _run(tmp_path, repo, rows):
    receipt = tmp_path / "receipts.jsonl"
    receipt.write_text("\n".join(row if isinstance(row, str) else json.dumps(row)
                                 for row in rows) + "\n")
    done = subprocess.run([sys.executable, str(SCRIPT), "--repo", str(repo), str(receipt)],
                          text=True, capture_output=True)
    return done, json.loads(done.stdout)


def _pairs(repo, base, candidate, count, base_pass=False, candidate_pass=True):
    return [row for number in range(count) for row in (
        _row(repo, base, candidate, str(number), "base", base_pass),
        _row(repo, base, candidate, str(number), "candidate", candidate_pass))]


def test_five_lifts_are_eligible(repo, tmp_path):
    root, base, candidate = repo
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    done, report = _run(tmp_path, root, _pairs(root, base, candidate, 5))
    assert done.returncode == 0
    assert report == {"n_tasks": 5, "base_pass": 0, "cand_pass": 5,
                      "b": 0, "c": 5, "eligible_for_steward_review": True,
                      "errors": []}
    assert _run(tmp_path, root, _pairs(root, base, candidate, 5))[1] == report
    assert {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_negative_transfer_is_ineligible(repo, tmp_path):
    root, base, candidate = repo
    rows = _pairs(root, base, candidate, 5)
    rows += [_row(root, base, candidate, "negative", "base", True),
             _row(root, base, candidate, "negative", "candidate", False)]
    done, report = _run(tmp_path, root, rows)
    assert done.returncode == 1
    assert report["b"] == 1 and report["c"] == 5
    assert not report["eligible_for_steward_review"] and not report["errors"]


def test_four_lifts_are_ineligible(repo, tmp_path):
    root, base, candidate = repo
    done, report = _run(tmp_path, root, _pairs(root, base, candidate, 4))
    assert done.returncode == 1
    assert report["b"] == 0 and report["c"] == 4
    assert not report["eligible_for_steward_review"] and not report["errors"]


def test_tampered_blob_fails_closed(repo, tmp_path):
    root, base, candidate = repo
    rows = _pairs(root, base, candidate, 5)
    rows[1]["skill_blob_sha"] = "0" * 40
    done, report = _run(tmp_path, root, rows)
    assert done.returncode == 1 and report["errors"]
    for all_candidates in (False, True):
        rows = _pairs(root, base, candidate, 5)
        for row in rows[1::2] if all_candidates else [rows[1]]:
            row.update(skill_commit=base,
                       skill_blob_sha=_git(root, "rev-parse", f"{base}:skills/SKILL.md"))
        done, report = _run(tmp_path, root, rows)
        assert done.returncode == 1 and report["errors"]
    rows = _pairs(root, base, candidate, 5)
    rows[1].update(skill_path="skills",
                   skill_blob_sha=_git(root, "rev-parse", f"{candidate}:skills"))
    done, report = _run(tmp_path, root, rows)
    assert done.returncode == 1 and report["errors"]


def test_mismatched_task_sets_fail_closed(repo, tmp_path):
    root, base, candidate = repo
    rows = [_row(root, base, candidate, "base-only", "base", False),
            _row(root, base, candidate, "candidate-only", "candidate", True)]
    done, report = _run(tmp_path, root, rows)
    assert done.returncode == 1 and report["errors"]
    rows = _pairs(root, base, candidate, 5)
    rows[0]["task_set_sha256"] = "b" * 64
    done, report = _run(tmp_path, root, rows)
    assert done.returncode == 1 and report["errors"]


def test_duplicate_task_arm_fails_closed(repo, tmp_path):
    root, base, candidate = repo
    rows = _pairs(root, base, candidate, 5)
    rows.append(dict(rows[0]))
    done, report = _run(tmp_path, root, rows)
    assert done.returncode == 1 and report["errors"]


def test_extra_and_duplicate_json_keys_fail_closed(repo, tmp_path):
    root, base, candidate = repo
    rows = _pairs(root, base, candidate, 5)
    extra = dict(rows[0], unexpected=True)
    done, report = _run(tmp_path, root, [extra, *rows[1:]])
    assert done.returncode == 1 and report["errors"]
    duplicate = json.dumps(rows[0])[:-1] + ',"task_id":"again"}'
    done, report = _run(tmp_path, root, [duplicate, *rows[1:]])
    assert done.returncode == 1 and report["errors"]
    for malformed in [{"passed": True}, [], {}, "", "not-json"]:
        done, report = _run(tmp_path, root, [malformed, *rows[1:]])
        assert done.returncode == 1 and report["errors"]
    done, report = _run(tmp_path, root, [])
    assert done.returncode == 1 and report["errors"]


def test_non_boolean_passed_fails_closed(repo, tmp_path):
    root, base, candidate = repo
    for value in (1, 0, "true", None, []):
        rows = _pairs(root, base, candidate, 5)
        rows[0]["passed"] = value
        done, report = _run(tmp_path, root, rows)
        assert done.returncode == 1 and report["errors"]
    for key in ("run_ref", "skill_path", "skill_commit", "skill_blob_sha", "task_id",
                "schema", "arm", "task_set_sha256"):
        rows = _pairs(root, base, candidate, 5)
        rows[0][key] = ""
        done, report = _run(tmp_path, root, rows)
        assert done.returncode == 1 and report["errors"]
