"""Composition and hostile-input controls for the four manifest profiles."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import verify_pack_boundary as verifier


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    shutil.copy2(REPO / "BOUNDARY.md", root / "BOUNDARY.md")
    shutil.copytree(REPO / ".agents/skills", root / ".agents/skills")
    shutil.copytree(REPO / "packs", root / "packs")
    return root


def test_real_checkout_and_fixture_have_exact_runtime_projection(repo):
    for root in [REPO, repo]:
        result = verifier.verify_pack_boundary(root)
        assert result["ok"] is True
        assert {k: len(v) for k, v in result["packs"].items()} == {
            "core": 6, "meta": 5, "research": 8, "brain": 4}
        assert result["packs"]["core"] == [
            "fallback", "gate-check", "resume-state", "run-log", "spawn-contract", "validate"]
        assert result["total_skills"] == 24
        assert result["manifested_skills"] == 23
        assert result["excluded_dev_core"] == ["slip-ladder"]
        assert result["runtime_conformance_verified"] is False


def test_read_only_deterministic_result_binds_consumed_bytes(repo):
    before = {str(p.relative_to(repo)): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    result = verifier.verify_pack_boundary(repo)
    assert result == verifier.verify_pack_boundary(repo)
    assert len(result["input_sha256"]) == 29
    for name, digest in result["input_sha256"].items():
        assert digest == hashlib.sha256(before[name]).hexdigest()
    assert before == {str(p.relative_to(repo)): p.read_bytes() for p in repo.rglob("*") if p.is_file()}


@pytest.mark.parametrize("pack", ["core", "meta", "research", "brain"])
def test_missing_empty_or_incomplete_manifest_fails_closed(repo, pack):
    path = repo / "packs" / (pack + ".txt")
    original = path.read_text()
    path.unlink()
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)
    path.write_text("# comments only\n")
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)
    lines = original.splitlines()
    first = next(line for line in lines if line and not line.startswith("#"))
    path.write_text("\n".join(line for line in lines if line != first) + "\n")
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("pack", ["core", "meta", "research", "brain"])
def test_duplicate_manifest_entries_fail_closed(repo, pack):
    path = repo / "packs" / (pack + ".txt")
    text = path.read_text()
    first = next(line for line in text.splitlines() if line and not line.startswith("#"))
    path.write_text(text + first + "\n")
    with pytest.raises(verifier.BoundaryError, match="duplicate"):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("entry", ["../ship", "/tmp/ship", "research/ship", "Ship", "missing-skill"])
def test_invalid_or_unknown_manifest_entries_fail_closed(repo, entry):
    path = repo / "packs/research.txt"
    path.write_text(path.read_text() + entry + "\n")
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("skill", ["ship", "brain-recall", "orchestrate", "slip-ladder"])
def test_dev_only_skill_cannot_enter_runtime_manifest(repo, skill):
    path = repo / "packs/core.txt"
    path.write_text(path.read_text() + skill + "\n")
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


def test_cross_pack_duplicate_or_extra_manifest_rejected(repo):
    path = repo / "packs/meta.txt"
    path.write_text(path.read_text() + "health\n")
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)
    path.write_text((REPO / "packs/meta.txt").read_text())
    (repo / "packs/extra.txt").write_text("health\n")
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("before,after", [
    ("layer: A", "layer: B"), ("runtime-safe: true", "runtime-safe: false"),
    ("runtime-safe: true", "runtime-safe: True"), ("pack: core", "pack: brain"),
    ("name: fallback", "name: ship"), ("layer: A", "layer: Z"),
    ("pack: core", "pack: unknown"), ("description:", "missing-description:"),
])
def test_tampered_required_frontmatter_fails_closed(repo, before, after):
    path = repo / ".agents/skills/fallback/SKILL.md"
    text = path.read_text()
    assert before in text
    path.write_text(text.replace(before, after, 1))
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("kind", ["absent", "unclosed", "duplicate", "empty", "structured", "empty-body"])
def test_malformed_frontmatter_or_body_is_rejected(repo, kind):
    path = repo / ".agents/skills/fallback/SKILL.md"
    text = path.read_text()
    if kind == "absent":
        text = text[4:]
    elif kind == "unclosed":
        text = text.replace("\n---\n", "\n", 1)
    elif kind == "duplicate":
        text = text.replace("\n---\n", "\nruntime-safe: false\n---\n", 1)
    elif kind == "empty":
        text = "---\n---\n# empty\n"
    elif kind == "structured":
        text = text.replace("pack: core", "pack: {value: core}", 1)
    else:
        text = "---" + text.split("---", 2)[1] + "---\n"
    path.write_text(text)
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("skill", ["fallback", "health"])
def test_missing_skill_file_fails_closed(repo, skill):
    (repo / ".agents/skills" / skill / "SKILL.md").unlink()
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


def test_unmanifested_skill_and_unrecognized_inventory_entry_fail_closed(repo):
    directory = repo / ".agents/skills/new-skill"
    directory.mkdir()
    text = (repo / ".agents/skills/health/SKILL.md").read_text()
    (directory / "SKILL.md").write_text(text.replace("name: health", "name: new-skill", 1))
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("kind", ["changed-name", "missing-heading", "duplicate-heading"])
def test_boundary_declaration_tampering_fails_closed(repo, kind):
    path = repo / "BOUNDARY.md"
    text = path.read_text()
    if kind == "changed-name":
        tick = chr(96)
        text = text.replace(tick + "fallback" + tick, tick + "ship" + tick)
    elif kind == "missing-heading":
        text = text.replace("**Runtime-safe core — Layer A**", "**Unknown core**")
    else:
        text += "\n" + text
    path.write_text(text)
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


@pytest.mark.parametrize("relative", [
    "BOUNDARY.md", "packs", "packs/core.txt", ".agents/skills",
    ".agents/skills/fallback", ".agents/skills/fallback/SKILL.md",
])
def test_symlink_escape_is_refused_even_with_identical_target_bytes(repo, tmp_path, relative):
    source = repo / relative
    outside = tmp_path / "outside"
    source.rename(outside)
    source.symlink_to(outside, target_is_directory=outside.is_dir())
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


def test_symlinked_root_and_internal_symlink_are_also_refused(repo, tmp_path):
    link = tmp_path / "root-link"
    link.symlink_to(repo, target_is_directory=True)
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(link)
    path = repo / "packs/core.txt"
    target = repo / "core-copy"
    target.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


def test_file_entry_and_encoding_limits_fail_closed(repo, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(verifier, "MAX_FILE_BYTES", 10)
        with pytest.raises(verifier.BoundaryError):
            verifier.verify_pack_boundary(repo)
    with monkeypatch.context() as m:
        m.setattr(verifier, "MAX_ENTRIES", 0)
        with pytest.raises(verifier.BoundaryError):
            verifier.verify_pack_boundary(repo)
    (repo / "packs/core.txt").write_bytes(b"\xff")
    with pytest.raises(verifier.BoundaryError):
        verifier.verify_pack_boundary(repo)


def test_cli_portability_valid_failure_and_fifo_refusal(repo, tmp_path):
    command = [sys.executable, str(REPO / "scripts/verify_pack_boundary.py")]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    good = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=5)
    assert good.returncode == 0 and json.loads(good.stdout)["ok"] is True
    assert good.stderr == ""
    path = repo / "packs/core.txt"
    path.unlink()
    os.mkfifo(path)
    bad = subprocess.run(command + ["--repo-root", str(repo)], cwd=tmp_path, env=env,
                         capture_output=True, text=True, timeout=5)
    assert bad.returncode != 0 and json.loads(bad.stdout)["ok"] is False
    assert bad.stderr == ""
