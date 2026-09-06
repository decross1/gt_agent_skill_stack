import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import brain_deploy


class FakeRunner:
    def __init__(self, source: Path, *, fingerprint: str = "a" * 40, dirty: bool = False, restart_code: int = 0, active: bool = True):
        self.source = source.resolve()
        self.fingerprint = fingerprint
        self.dirty = dirty
        self.restart_code = restart_code
        self.active = active
        self.commands: list[list[str]] = []

    def __call__(self, command, **_kwargs):
        command = list(command)
        self.commands.append(command)
        if command[0] == "git":
            arguments = command[3:]
            if arguments == ["rev-parse", "--show-toplevel"]:
                return self.result(command, 0, f"{self.source}\n")
            if arguments == ["rev-parse", "--git-path", "index.lock"]:
                return self.result(command, 0, ".git/index.lock\n")
            if arguments == ["rev-parse", "--verify", "refs/heads/main^{commit}"]:
                return self.result(command, 0, f"{self.fingerprint}\n")
            if arguments == ["rev-parse", "HEAD^{commit}"]:
                return self.result(command, 0, f"{self.fingerprint}\n")
            if arguments == ["symbolic-ref", "--quiet", "--short", "HEAD"]:
                return self.result(command, 0, "main\n")
            if arguments == ["diff", "--cached", "--name-only"]:
                return self.result(command, 0)
            if arguments[:3] == ["status", "--porcelain", "--untracked-files=all"]:
                return self.result(command, 0, " M changed.py\n" if self.dirty else "")
            if arguments[:3] == ["ls-tree", "-r", "--full-tree"]:
                return self.result(command, 0, self.fingerprint)
        if command[:3] == ["systemctl", "--user", "restart"]:
            return self.result(command, self.restart_code, stderr="restart failed" if self.restart_code else "")
        if command[:4] == ["systemctl", "--user", "is-active", "--quiet"]:
            return self.result(command, 0 if self.active else 3)
        raise AssertionError(f"unexpected command: {command}")

    @staticmethod
    def result(command, returncode, stdout="", stderr=""):
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)


@pytest.fixture
def deployment_paths(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / ".git").mkdir()
    monkeypatch.setattr(brain_deploy, "service_ready", lambda: True)
    return source, tmp_path / "state" / "brain-deploy-state.json"


def restart_commands(runner):
    return [command for command in runner.commands if command[:3] == ["systemctl", "--user", "restart"]]


def test_new_clean_fingerprint_restarts_then_records(deployment_paths):
    source, state = deployment_paths
    state.parent.mkdir()
    state.write_text(json.dumps({"schema_version": 1, "fingerprint": "b" * 40}) + "\n")
    runner = FakeRunner(source)

    result = brain_deploy.deploy(source, state, "main", "brain.service", runner)

    assert result.status == "restarted"
    assert len(restart_commands(runner)) == 1
    assert json.loads(state.read_text())["fingerprint"] == hashlib.sha256(b"a" * 40).hexdigest()


def test_duplicate_ref_event_does_not_restart(deployment_paths):
    source, state = deployment_paths
    state.parent.mkdir()
    state.write_text(json.dumps({"schema_version": 1, "fingerprint": hashlib.sha256(b"a" * 40).hexdigest()}) + "\n")
    runner = FakeRunner(source)

    result = brain_deploy.deploy(source, state, "main", "brain.service", runner)

    assert result.status == "unchanged"
    assert restart_commands(runner) == []


def test_dirty_source_defers_without_service_action(deployment_paths):
    source, state = deployment_paths
    runner = FakeRunner(source, dirty=True)

    result = brain_deploy.deploy(source, state, "main", "brain.service", runner)

    assert result.status == "deferred"
    assert "uncommitted" in result.detail
    assert restart_commands(runner) == []
    assert not state.exists()


def test_index_lock_defers_without_service_action(deployment_paths):
    source, state = deployment_paths
    (source / ".git" / "index.lock").write_text("")
    runner = FakeRunner(source)

    result = brain_deploy.deploy(source, state, "main", "brain.service", runner)

    assert result.status == "deferred"
    assert "index is busy" in result.detail
    assert restart_commands(runner) == []


def test_restart_failure_preserves_previous_fingerprint(deployment_paths):
    source, state = deployment_paths
    state.parent.mkdir()
    state.write_text(json.dumps({"schema_version": 1, "fingerprint": "b" * 40}) + "\n")
    runner = FakeRunner(source, restart_code=1)

    with pytest.raises(brain_deploy.DeploymentError, match="cannot restart"):
        brain_deploy.deploy(source, state, "main", "brain.service", runner)

    assert json.loads(state.read_text())["fingerprint"] == "b" * 40
    assert len(restart_commands(runner)) == 1


def test_inactive_service_cannot_record_success(deployment_paths):
    source, state = deployment_paths
    runner = FakeRunner(source, active=False)
    with pytest.raises(brain_deploy.DeploymentError, match="not active"):
        brain_deploy.deploy(source, state, "main", "brain.service", runner)
    assert not state.exists()


@pytest.fixture
def real_source(tmp_path):
    root = tmp_path / "real-source"
    root.mkdir()
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()
    git("init", "-b", "main")
    git("config", "user.name", "Synthetic deployment fixture")
    git("config", "user.email", "fixture@example.invalid")
    for path, content in {"scripts/app.py": "pass\n", "AGENTS.md": "fixture authority\n",
                          "memory/brain/narratives.jsonl": "{}\n", "docs/note.md": "note\n"}.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    git("add", ".")
    git("commit", "-m", "Synthetic baseline")
    return root, git


def test_operator_and_ledger_changes_do_not_dirty_runtime_source(real_source):
    source, _git = real_source
    (source / "AGENTS.md").write_text("preserved operator authority\n")
    (source / "memory/brain/narratives.jsonl").write_text("{}\n{}\n")
    (source / "handoffs").mkdir()
    (source / "handoffs/private.md").write_text("private audit fixture\n")
    assert brain_deploy.source_fingerprint(source, "main", subprocess.run).status == "ready"


def test_non_runtime_commit_keeps_source_fingerprint(real_source):
    source, git = real_source
    before = brain_deploy.source_fingerprint(source, "main", subprocess.run)
    (source / "docs/note.md").write_text("documentation only\n")
    git("add", "docs/note.md")
    git("commit", "-m", "No runtime source changes")
    after = brain_deploy.source_fingerprint(source, "main", subprocess.run)
    assert before.fingerprint == after.fingerprint


def test_another_branch_at_main_commit_is_not_a_main_deployment(real_source):
    source, git = real_source
    git("switch", "-c", "unreleased")
    assert brain_deploy.source_fingerprint(source, "main", subprocess.run).status == "deferred"


def test_runtime_dirt_and_staged_index_defer(real_source):
    source, git = real_source
    (source / "scripts/app.py").write_text("uncommitted = True\n")
    assert brain_deploy.source_fingerprint(source, "main", subprocess.run).status == "deferred"
    (source / "scripts/app.py").write_text("pass\n")
    (source / "docs/note.md").write_text("staged edit\n")
    git("add", "docs/note.md")
    assert brain_deploy.source_fingerprint(source, "main", subprocess.run).status == "deferred"


def test_active_process_without_ready_api_does_not_record_success(deployment_paths, monkeypatch):
    source, state = deployment_paths
    monkeypatch.setattr(brain_deploy, "service_ready", lambda: False, raising=False)
    runner = FakeRunner(source, active=True)
    with pytest.raises(brain_deploy.DeploymentError, match="readiness"):
        brain_deploy.deploy(source, state, "main", "brain.service", runner)
    assert not state.exists()


@pytest.mark.parametrize("summary,operations,expected", [
    ({"status_strip": {}}, {"read_only": True, "server": {"alive": {"value": True}}}, True),
    ({"error": "old API"}, {"read_only": True, "server": {"alive": {"value": True}}}, False),
    ({"status_strip": {}}, {"error": "no route"}, False),
    ({"status_strip": {}}, {"read_only": True, "server": {"alive": {"value": "true"}}}, False),
])
def test_readiness_checks_both_supported_api_shapes(monkeypatch, summary, operations, expected):
    class Opener:
        def open(self, url, **kwargs):
            assert url.startswith("http://127.0.0.1:5180/api/")
            return io.BytesIO(json.dumps(summary if url.endswith("summary") else operations).encode())
    monkeypatch.setattr(brain_deploy.urllib.request, "build_opener", lambda *_: Opener())
    monkeypatch.setattr(brain_deploy.time, "sleep", lambda _: None)
    assert brain_deploy.service_ready() is expected
