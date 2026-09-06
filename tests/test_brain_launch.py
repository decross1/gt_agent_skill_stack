"""Private-fixture tests for the separately installed Brain launcher.

Every subprocess is local and finite.  The fixtures never invoke systemd, bind a
socket, call an API, or touch the canonical Brain ledgers.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
LAUNCHER_TEMPLATE = REPO / "systemd" / "libexec" / "brain-launch.py"


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None,
         timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _git(source: Path, *arguments: str) -> str:
    result = _run(["git", "-C", str(source), *arguments], cwd=source)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _insert_after_future(path: Path, statement: str) -> None:
    content = path.read_text()
    future = "from __future__ import annotations\n"
    assert content.startswith(future)
    path.write_text(future + statement + content[len(future):])


@pytest.fixture
def launch_fixture(tmp_path: Path) -> dict[str, Path | str]:
    source = tmp_path / "agent_system"
    source.mkdir()
    state_root = tmp_path / "private-state"
    state_root.mkdir(mode=0o700)
    installed_dir = tmp_path / "installed"
    installed_dir.mkdir(mode=0o700)
    installed = installed_dir / "brain-launch.py"
    shutil.copyfile(LAUNCHER_TEMPLATE, installed)
    installed.chmod(0o700)

    helper_report = tmp_path / "helper-report.json"
    server_report = tmp_path / "server-report.json"
    child_report = tmp_path / "child-report.json"
    helper_state = state_root / "brain-deploy-state.json"
    selection = state_root / "selected-release.json"

    helper = '''\
from __future__ import annotations
import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

@dataclass
class ModuleProbe:
    identity: ClassVar[str] = "verified-helper"

ROOT = Path(__file__).resolve().parent.parent
Path(os.environ["FIXTURE_HELPER_REPORT"]).write_text(json.dumps({
    "file": __file__, "root": str(ROOT), "executable": sys.executable,
    "isolated": sys.flags.isolated, "module_file": sys.modules[__name__].__file__,
}))

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--state", required=True)
parser.add_argument("--branch", required=True)
parser.add_argument("--service", required=True)
parser.add_argument("--release-manifest", required=True)
parser.add_argument("--release-manifest-sha256", required=True)
parser.add_argument("--selection", required=True)
args = parser.parse_args()
status = os.environ.get("FIXTURE_HELPER_STATUS", "applied")
if status == "deferred":
    raise SystemExit(20)
if status == "failed":
    raise SystemExit(1)
manifest = json.loads(Path(args.release_manifest).read_text())
if status == "applied":
    Path(args.state).write_text(json.dumps({
        "schema_version": 2,
        "fingerprint": manifest["runtime_fingerprint"],
        "manifest_sha256": args.release_manifest_sha256,
    }) + "\\n")
raise SystemExit(0)
'''
    server = '''\
import json
import os
import subprocess
import sys
from pathlib import Path
from support import SUPPORT_FILE, VALUE
import fractions

ROOT = Path(__file__).resolve().parent.parent
child = Path(os.environ["FIXTURE_CHILD_REPORT"])
proc = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "review_proposal_cli.py"),
     "--output", str(child)],
    text=True, capture_output=True, timeout=10,
)
Path(os.environ["FIXTURE_SERVER_REPORT"]).write_text(json.dumps({
    "file": __file__, "root": str(ROOT),
    "view": str(ROOT / "memory" / "brain" / "view"),
    "consumer": str(ROOT.parent / "a_bgt_rsi"),
    "data": (ROOT / "memory" / "brain" / "operator-data.txt").read_text(),
    "support_file": SUPPORT_FILE, "support_value": VALUE,
    "collision_file": fractions.__file__, "collision_value": fractions.VALUE,
    "executable": sys.executable, "isolated": sys.flags.isolated,
    "child_returncode": proc.returncode, "child_stderr": proc.stderr,
}))
'''
    support = '''\
SUPPORT_FILE = __file__
VALUE = "pinned-support"
'''
    collision = '''\
VALUE = "pinned-local-fractions"
'''
    child = '''\
import argparse
import json
import sys
from pathlib import Path
from support import SUPPORT_FILE, VALUE

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True)
args = parser.parse_args()
Path(args.output).write_text(json.dumps({
    "file": __file__, "root": str(ROOT), "support_file": SUPPORT_FILE,
    "support_value": VALUE, "executable": sys.executable,
    "isolated": sys.flags.isolated,
}))
'''
    for path, content in {
        "scripts/brain_deploy.py": helper,
        "scripts/brain_server.py": server,
        "scripts/support.py": support,
        "scripts/fractions.py": collision,
        "scripts/review_proposal_cli.py": child,
        "scripts/project_pages.py": "REPO = __import__('pathlib').Path(__file__).resolve().parent.parent\n",
        "scripts/project_map.py": "VALUE = 'map'\n",
        "scripts/project_summary.py": "VALUE = 'summary'\n",
        "memory/brain/view/dashboard.html": "<!doctype html><title>fixture</title>\n",
        "memory/brain/operator-data.txt": "canonical-data-v1\n",
        "systemd/libexec/brain-launch.py": LAUNCHER_TEMPLATE.read_text(),
        "systemd/user/brain.service": "[Service]\n",
        "AGENTS.md": "fixture authority\n",
        "docs/note.md": "fixture docs v1\n",
    }.items():
        _write(source / path, content)

    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "Launcher fixture")
    _git(source, "config", "user.email", "launcher@example.invalid")
    _git(source, "add", ".")
    _git(source, "commit", "-m", "fixture baseline")

    return {
        "source": source,
        "state_root": state_root,
        "installed": installed,
        "selection": selection,
        "helper_state": helper_state,
        "helper_report": helper_report,
        "server_report": server_report,
        "child_report": child_report,
    }


def _common(fx: dict[str, Path | str]) -> list[str]:
    return [
        "--source", str(fx["source"]),
        "--branch", "main",
        "--state-root", str(fx["state_root"]),
        "--selection", str(fx["selection"]),
    ]


def _launcher(fx: dict[str, Path | str], mode: str, *,
              env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-I", str(fx["installed"]), mode, *_common(fx)]
    if mode in ("prepare", "deploy"):
        command += ["--helper-state", str(fx["helper_state"]), "--service", "brain.service"]
    if mode == "serve":
        command += ["--host", "0.0.0.0", "--port", "5180"]
    fixture_env = {
        "FIXTURE_HELPER_REPORT": str(fx["helper_report"]),
        "FIXTURE_SERVER_REPORT": str(fx["server_report"]),
        "FIXTURE_CHILD_REPORT": str(fx["child_report"]),
    }
    return _run(command, cwd=Path(fx["source"]), env={**fixture_env, **(env or {})})


def _descriptor(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


def _selection(fx: dict[str, Path | str]) -> dict:
    return json.loads(Path(fx["selection"]).read_text())


def _activate(fx: dict[str, Path | str]) -> dict:
    result = _launcher(fx, "deploy")
    assert result.returncode == 0, result.stderr
    selected = _selection(fx)
    assert selected["candidate"] is None
    assert selected["active"] is not None
    return selected


def test_direct_dirty_helper_executes_marker_before_argument_validation(launch_fixture):
    """The historical direct-Python ordering executes dirty top-level code."""
    fx = launch_fixture
    source = Path(fx["source"])
    marker = source.parent / "direct-dirty-helper.marker"
    helper = source / "scripts" / "brain_deploy.py"
    _insert_after_future(
        helper, f"from pathlib import Path\nPath({str(marker)!r}).write_text('dirty')\n",
    )
    result = _run([sys.executable, str(helper)], cwd=source,
                  env={"FIXTURE_HELPER_REPORT": str(fx["helper_report"])})
    assert result.returncode != 0
    assert marker.read_text() == "dirty"


def test_dirty_helper_is_blocked_before_checkout_python_starts(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    marker = source.parent / "dirty-helper.marker"
    helper = source / "scripts" / "brain_deploy.py"
    _insert_after_future(
        helper, f"from pathlib import Path\nPath({str(marker)!r}).write_text('dirty')\n",
    )

    result = _launcher(fx, "deploy")

    assert result.returncode == 20
    assert "runtime" in result.stderr
    assert not marker.exists()
    assert not Path(fx["helper_report"]).exists()
    assert not Path(fx["selection"]).exists()


def test_assume_unchanged_cannot_hide_dirty_helper_marker(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    marker = source.parent / "assume-unchanged-helper.marker"
    helper = source / "scripts" / "brain_deploy.py"
    _git(source, "update-index", "--assume-unchanged", "scripts/brain_deploy.py")
    _insert_after_future(
        helper, f"from pathlib import Path\nPath({str(marker)!r}).write_text('dirty')\n",
    )
    assert _git(source, "status", "--porcelain", "--", "scripts/brain_deploy.py") == ""

    result = _launcher(fx, "deploy")

    assert result.returncode == 20
    assert "working bytes" in result.stderr
    assert not marker.exists()
    assert not Path(fx["helper_report"]).exists()


def test_dirty_server_is_blocked_on_normal_restart_entrypoint(launch_fixture):
    fx = launch_fixture
    _activate(fx)
    Path(fx["server_report"]).unlink(missing_ok=True)
    source = Path(fx["source"])
    marker = source.parent / "dirty-server.marker"
    server = source / "scripts" / "brain_server.py"
    server.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('dirty')\n" + server.read_text())

    result = _launcher(fx, "serve")

    assert result.returncode == 20
    assert not marker.exists()
    assert not Path(fx["server_report"]).exists()


def test_clean_modes_keep_canonical_roots_and_use_pinned_child_interpreter(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    _activate(fx)
    # Canonical mutable data and unrelated operator dirt remain live and allowed.
    (source / "memory" / "brain" / "operator-data.txt").write_text("canonical-data-v2\n")
    (source / "AGENTS.md").write_text("preserved operator authority\n")
    _write(source / "handoffs" / "private.md", "untracked operator handoff\n")

    result = _launcher(fx, "serve")

    assert result.returncode == 0, result.stderr
    helper = json.loads(Path(fx["helper_report"]).read_text())
    server = json.loads(Path(fx["server_report"]).read_text())
    child = json.loads(Path(fx["child_report"]).read_text())
    canonical_scripts = source / "scripts"
    assert helper["file"] == str(canonical_scripts / "brain_deploy.py")
    assert helper["module_file"] == str(canonical_scripts / "brain_deploy.py")
    assert helper["root"] == str(source)
    assert server["file"] == str(canonical_scripts / "brain_server.py")
    assert server["root"] == str(source)
    assert server["view"] == str(source / "memory" / "brain" / "view")
    assert server["consumer"] == str(source.parent / "a_bgt_rsi")
    assert server["data"] == "canonical-data-v2\n"
    assert server["support_file"] == str(canonical_scripts / "support.py")
    assert server["support_value"] == "pinned-support"
    assert server["collision_file"] == str(canonical_scripts / "fractions.py")
    assert server["collision_value"] == "pinned-local-fractions"
    assert server["executable"] == str(fx["installed"])
    assert server["isolated"] == 1
    assert server["child_returncode"] == 0
    assert child["file"] == str(canonical_scripts / "review_proposal_cli.py")
    assert child["root"] == str(source)
    assert child["support_file"] == str(canonical_scripts / "support.py")
    assert child["executable"] == str(fx["installed"])
    assert child["isolated"] == 1
    assert (source / "AGENTS.md").read_text() == "preserved operator authority\n"
    assert (source / "handoffs" / "private.md").read_text() == "untracked operator handoff\n"


def test_prepare_materializes_exact_raw_git_blobs_and_frozen_descriptor(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    result = _launcher(fx, "prepare")
    descriptor = _descriptor(result)
    manifest_path = Path(descriptor["manifest_path"])
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)

    assert hashlib.sha256(manifest_bytes).hexdigest() == descriptor["manifest_sha256"]
    assert manifest["runtime_fingerprint"] == descriptor["runtime_fingerprint"]
    assert manifest["source_root"] == str(source)
    assert manifest["snapshot_root"] == descriptor["snapshot_root"]
    assert manifest["launcher_identity"] == descriptor["launcher_identity"]
    assert manifest["entrypoints"] == descriptor["entrypoints"]
    assert manifest["entrypoints"]["serve"]["cwd"] == str(source)
    assert manifest["entrypoints"]["serve"]["argv"][0] == sys.executable
    assert manifest["entrypoints"]["serve"]["argv"][1] == "-I"
    entries = {entry["path"]: entry for entry in manifest["files"]}
    for relative in ("scripts/brain_server.py", "scripts/support.py", "memory/brain/view/dashboard.html"):
        raw = subprocess.run(
            ["git", "-C", str(source), "show", f"HEAD:{relative}"],
            capture_output=True, check=True,
        ).stdout
        snapshot = Path(manifest["snapshot_root"]) / relative
        assert snapshot.read_bytes() == raw
        assert hashlib.sha256(raw).hexdigest() == entries[relative]["sha256"]
    assert (Path(manifest["release_root"]).stat().st_mode & 0o222) == 0
    assert (manifest_path.stat().st_mode & 0o222) == 0


@pytest.mark.parametrize("failure", ["runtime", "staged", "branch", "index_lock"])
def test_source_admission_failures_are_deferred_without_python(launch_fixture, failure):
    fx = launch_fixture
    source = Path(fx["source"])
    if failure == "runtime":
        (source / "scripts" / "support.py").write_text("VALUE = 'dirty'\n")
    elif failure == "staged":
        (source / "docs" / "note.md").write_text("staged docs\n")
        _git(source, "add", "docs/note.md")
    elif failure == "branch":
        _git(source, "switch", "-c", "unreleased")
    else:
        git_dir = Path(_git(source, "rev-parse", "--git-dir"))
        if not git_dir.is_absolute():
            git_dir = source / git_dir
        (git_dir / "index.lock").write_text("")

    result = _launcher(fx, "deploy")

    assert result.returncode == 20
    assert not Path(fx["helper_report"]).exists()
    assert not Path(fx["selection"]).exists()


def test_local_fsmonitor_command_never_runs_before_admission(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    marker = source.parent / "fsmonitor.marker"
    monitor = source.parent / "fsmonitor-hook.py"
    monitor.write_text(
        "#!/usr/bin/python3\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
    )
    monitor.chmod(0o700)
    _git(source, "config", "core.fsmonitor", str(monitor))

    result = _launcher(fx, "deploy")

    assert result.returncode == 0, result.stderr
    assert not marker.exists()


def test_local_clean_filter_command_never_runs_before_admission(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    attributes = source / ".gitattributes"
    attributes.write_text("scripts/*.py filter=prelaunch\n")
    _git(source, "add", ".gitattributes")
    _git(source, "commit", "-m", "fixture attributes")
    marker = source.parent / "clean-filter.marker"
    filter_program = source.parent / "clean-filter.py"
    filter_program.write_text(
        "#!/usr/bin/python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n"
    )
    filter_program.chmod(0o700)
    _git(source, "config", "filter.prelaunch.clean", str(filter_program))
    helper = source / "scripts" / "brain_deploy.py"
    info = helper.stat()
    os.utime(helper, ns=(info.st_atime_ns, max(info.st_mtime_ns + 2_000_000_000, time.time_ns())))

    result = _launcher(fx, "deploy")

    assert result.returncode == 0, result.stderr
    assert not marker.exists()


@pytest.mark.parametrize("target", ["snapshot", "manifest", "selector"])
def test_release_or_selector_tamper_fails_before_server_execution(launch_fixture, target):
    fx = launch_fixture
    selected = _activate(fx)
    Path(fx["server_report"]).unlink(missing_ok=True)
    active = selected["active"]
    manifest_path = Path(active["manifest_path"])
    manifest = json.loads(manifest_path.read_text())
    if target == "snapshot":
        path = Path(manifest["snapshot_root"]) / "scripts" / "brain_server.py"
        path.chmod(0o600)
        path.write_text("raise SystemExit('tampered snapshot executed')\n")
    elif target == "manifest":
        manifest_path.chmod(0o600)
        manifest_path.write_text(manifest_path.read_text() + " ")
    else:
        selector = Path(fx["selection"])
        payload = json.loads(selector.read_text())
        payload["active"]["manifest_sha256"] = "0" * 64
        selector.write_text(json.dumps(payload) + "\n")

    result = _launcher(fx, "serve")

    assert result.returncode == 21
    assert not Path(fx["server_report"]).exists()


def test_installed_path_and_hash_are_bound_to_release(launch_fixture):
    fx = launch_fixture
    _activate(fx)
    Path(fx["server_report"]).unlink(missing_ok=True)
    second = Path(fx["installed"]).with_name("brain-launch-second.py")
    shutil.copyfile(fx["installed"], second)
    second.chmod(0o700)
    command = [sys.executable, "-I", str(second), "serve", *_common(fx),
               "--host", "0.0.0.0", "--port", "5180"]
    result = _run(command, cwd=Path(fx["source"]), env={
        "FIXTURE_SERVER_REPORT": str(fx["server_report"]),
        "FIXTURE_CHILD_REPORT": str(fx["child_report"]),
    })
    assert result.returncode == 21
    assert not Path(fx["server_report"]).exists()


def test_committed_launcher_template_must_match_installed_bytes(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    template = source / "systemd" / "libexec" / "brain-launch.py"
    template.write_text(template.read_text() + "\n# reviewed replacement not installed yet\n")
    _git(source, "add", "systemd/libexec/brain-launch.py")
    _git(source, "commit", "-m", "new launcher template")

    result = _launcher(fx, "deploy")

    assert result.returncode == 20
    assert "installed launcher" in result.stderr
    assert not Path(fx["helper_report"]).exists()

    installed = Path(fx["installed"])
    installed.write_text(installed.read_text() + "\n# changed installed identity\n")
    result = _launcher(fx, "serve")
    assert result.returncode == 21
    assert not Path(fx["server_report"]).exists()


def test_docs_only_head_advance_keeps_restartable_active_release(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    before = _activate(fx)["active"]
    (source / "docs" / "note.md").write_text("fixture docs v2\n")
    _git(source, "add", "docs/note.md")
    _git(source, "commit", "-m", "docs only")

    result = _launcher(fx, "serve")

    assert result.returncode == 0, result.stderr
    assert _selection(fx)["active"] == before
    assert json.loads(Path(fx["server_report"]).read_text())["root"] == str(source)


def test_runtime_equal_noop_preserves_old_selector_and_applied_provenance(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    before = _activate(fx)["active"]
    state_before = Path(fx["helper_state"]).read_bytes()
    (source / "docs" / "note.md").write_text("fixture docs v2\n")
    _git(source, "add", "docs/note.md")
    _git(source, "commit", "-m", "docs only")

    result = _launcher(fx, "deploy", env={"FIXTURE_HELPER_STATUS": "noop"})

    assert result.returncode == 0, result.stderr
    assert _selection(fx) == {"schema_version": 1, "active": before, "candidate": None}
    assert Path(fx["helper_state"]).read_bytes() == state_before


def test_helper_failure_restores_selector_without_applied_write(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    before = _activate(fx)["active"]
    state_before = Path(fx["helper_state"]).read_bytes()
    (source / "scripts" / "support.py").write_text("SUPPORT_FILE = __file__\nVALUE = 'v2'\n")
    _git(source, "add", "scripts/support.py")
    _git(source, "commit", "-m", "runtime v2")

    result = _launcher(fx, "deploy", env={"FIXTURE_HELPER_STATUS": "failed"})

    assert result.returncode == 1
    assert _selection(fx) == {"schema_version": 1, "active": before, "candidate": None}
    assert Path(fx["helper_state"]).read_bytes() == state_before


def test_abandoned_candidate_is_never_used_after_transaction_lock_dies(launch_fixture):
    fx = launch_fixture
    source = Path(fx["source"])
    active = _activate(fx)["active"]
    Path(fx["server_report"]).unlink(missing_ok=True)
    (source / "scripts" / "support.py").write_text("SUPPORT_FILE = __file__\nVALUE = 'v2'\n")
    _git(source, "add", "scripts/support.py")
    _git(source, "commit", "-m", "runtime v2")
    candidate = _descriptor(_launcher(fx, "prepare"))
    abandoned = {
        "schema_version": 1,
        "active": active,
        "candidate": {
            "manifest_path": candidate["manifest_path"],
            "manifest_sha256": candidate["manifest_sha256"],
        },
    }
    Path(fx["selection"]).write_text(json.dumps(abandoned) + "\n")

    result = _launcher(fx, "serve")

    assert result.returncode == 20
    assert "selected release" in result.stderr
    assert not Path(fx["server_report"]).exists()


def test_launcher_requires_isolated_python(launch_fixture):
    fx = launch_fixture
    result = _run([sys.executable, str(fx["installed"]), "prepare", *_common(fx),
                   "--helper-state", str(fx["helper_state"]), "--service", "brain.service"],
                  cwd=Path(fx["source"]))
    assert result.returncode == 22
    assert "isolated" in result.stderr
