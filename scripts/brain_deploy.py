#!/usr/bin/env python3
"""Apply one launcher-prepared Brain release and prove the new service identity.

This helper is executed from a verified immutable release by the separately
installed ``brain-launch.py``.  It never prepares or selects a release itself.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable


Runner = Callable[..., subprocess.CompletedProcess[str]]
STATE_SCHEMA_VERSION = 2
MANIFEST_SCHEMA_VERSION = 1
EXIT_DEFERRED = 20
EXIT_INVALID = 21
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 20
TRANSACTION_TIMEOUT_SECONDS = 80.0
READINESS_TIMEOUT_SECONDS = 45.0
READINESS_POLL_SECONDS = 0.2
API_TIMEOUT_SECONDS = 3.0
EXPECTED_HOST = "0.0.0.0"
EXPECTED_PORT = 5180
EXPECTED_SERVICE = "brain.service"
MANAGED_UNITS = ("brain.service", "brain-deploy.service", "brain-deploy.path")
MAX_PROC_FILE_BYTES = 8 * 1024 * 1024
MAX_PROC_ROWS = 262_144
MAX_PROC_FDS = 1_048_576
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SOCKET_LINK = re.compile(r"^socket:\[(\d+)\]$")


class DeploymentError(RuntimeError):
    """Base class for a deployment outcome that cannot be called successful."""


class DeploymentDeferred(DeploymentError):
    """A safe, recoverable refusal; the launcher's candidate must not promote."""


class DeploymentInvalid(DeploymentError):
    """Invalid immutable input, durable state, or installed configuration."""


class ReadinessError(RuntimeError):
    """One point-in-time process, listener, or HTTP observation did not qualify."""


@dataclass(frozen=True)
class ReleaseManifest:
    path: Path
    manifest_sha256: str
    commit: str
    branch: str
    source_root: Path
    release_root: Path
    snapshot_root: Path
    runtime_fingerprint: str
    launcher_path: Path
    launcher_sha256: str
    serve_cwd: Path
    serve_argv: tuple[str, ...]
    selection_path: Path
    deploy_state_path: Path
    deploy_service: str
    payload: dict


@dataclass(frozen=True)
class ServiceObservation:
    active_state: str
    sub_state: str
    main_pid: int
    start_timestamp_monotonic: int


@dataclass(frozen=True)
class ServiceIdentity:
    main_pid: int
    start_timestamp_monotonic: int
    process_start_ticks: int
    cwd: str
    argv: tuple[str, ...]
    listener_inode: int


@dataclass(frozen=True)
class DeploymentResult:
    status: str
    detail: str
    fingerprint: str
    service: ServiceIdentity | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bounded(path: Path, limit: int, label: str) -> bytes:
    try:
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError as error:
        raise DeploymentInvalid(f"cannot read {label} {path}: {error}") from error
    if len(data) > limit:
        raise DeploymentInvalid(f"{label} exceeds {limit} bytes: {path}")
    return data


def _absolute_path(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise DeploymentInvalid(f"release manifest {field} must be a non-empty path")
    path = Path(value)
    if not path.is_absolute():
        raise DeploymentInvalid(f"release manifest {field} is not absolute")
    return path.resolve()


def _safe_runtime_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise DeploymentInvalid("release manifest file path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise DeploymentInvalid(f"release manifest file path is unsafe: {value}")
    if not (value.startswith("scripts/") or value.startswith("memory/brain/view/")):
        raise DeploymentInvalid(f"release manifest contains a non-runtime path: {value}")
    return value


def _argv_value(argv: tuple[str, ...], flag: str) -> str:
    positions = [index for index, token in enumerate(argv) if token == flag]
    if len(positions) != 1 or positions[0] + 1 >= len(argv):
        raise DeploymentInvalid(f"release manifest serve argv needs exactly one {flag}")
    return argv[positions[0] + 1]


def _validate_fixed_serve_argv(
    argv: tuple[str, ...], source: Path, branch: str
) -> tuple[Path, Path]:
    if _argv_value(argv, "--host") != EXPECTED_HOST or _argv_value(
        argv, "--port"
    ) != str(EXPECTED_PORT):
        raise DeploymentInvalid("release manifest changes the fixed Brain host or port")
    if Path(_argv_value(argv, "--source")).resolve() != source:
        raise DeploymentInvalid("release manifest serve argv has the wrong source")
    if _argv_value(argv, "--branch") != branch:
        raise DeploymentInvalid("release manifest serve argv has the wrong branch")
    state_root = _absolute_path(
        _argv_value(argv, "--state-root"), "entrypoints.serve.argv --state-root"
    )
    selection = _absolute_path(
        _argv_value(argv, "--selection"), "entrypoints.serve.argv --selection"
    )
    if not selection.is_relative_to(state_root) or selection == state_root:
        raise DeploymentInvalid("release manifest selection is outside state_root")
    return state_root, selection


def _validate_deploy_entrypoint(
    entrypoints: dict,
    *,
    source: Path,
    branch: str,
    launcher_path: Path,
    interpreter: str,
    state_root: Path,
    selection: Path,
) -> tuple[Path, str]:
    deploy = entrypoints.get("deploy")
    if not isinstance(deploy, dict):
        raise DeploymentInvalid("release manifest entrypoints.deploy is invalid")
    source_path = _safe_runtime_path(deploy.get("source_path"))
    if source_path != "scripts/brain_deploy.py":
        raise DeploymentInvalid("release manifest deploy source_path is not brain_deploy.py")
    deploy_cwd = _absolute_path(deploy.get("cwd"), "entrypoints.deploy.cwd")
    virtual_file = _absolute_path(
        deploy.get("virtual_file"), "entrypoints.deploy.virtual_file"
    )
    if deploy_cwd != source or virtual_file != source / source_path:
        raise DeploymentInvalid(
            "release manifest deploy entrypoint does not preserve the canonical source"
        )
    argv_value = deploy.get("argv")
    if (
        not isinstance(argv_value, list)
        or not argv_value
        or any(not isinstance(item, str) or not item for item in argv_value)
    ):
        raise DeploymentInvalid("release manifest deploy argv is invalid")
    argv = tuple(argv_value)
    helper_state = _absolute_path(
        _argv_value(argv, "--helper-state"),
        "entrypoints.deploy.argv --helper-state",
    )
    service = _argv_value(argv, "--service")
    if service != EXPECTED_SERVICE:
        raise DeploymentInvalid(
            f"release manifest deploy service must be {EXPECTED_SERVICE}"
        )
    if not helper_state.is_relative_to(state_root) or helper_state == state_root:
        raise DeploymentInvalid("release manifest helper state is outside state_root")
    if helper_state == selection:
        raise DeploymentInvalid("release manifest helper state and selection must differ")
    expected = (
        interpreter,
        "-I",
        str(launcher_path),
        "deploy",
        "--source",
        str(source),
        "--branch",
        branch,
        "--state-root",
        str(state_root),
        "--selection",
        str(selection),
        "--helper-state",
        str(helper_state),
        "--service",
        service,
    )
    if argv != expected:
        raise DeploymentInvalid(
            "release manifest deploy argv does not match the fixed launcher interface"
        )
    return helper_state, service


def load_release_manifest(
    path: Path,
    expected_sha256: str,
    source: Path,
    branch: str,
) -> ReleaseManifest:
    """Validate both manifest digests and the frozen launcher/deployment contract."""
    if not _HEX64.fullmatch(expected_sha256):
        raise DeploymentInvalid("release manifest digest must be lowercase SHA-256")
    path = path.resolve()
    raw = _read_bounded(path, MAX_MANIFEST_BYTES, "release manifest")
    actual_sha256 = _sha256_bytes(raw)
    if actual_sha256 != expected_sha256:
        raise DeploymentInvalid(
            f"release manifest digest mismatch: expected {expected_sha256}, observed {actual_sha256}"
        )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeploymentInvalid(f"release manifest is not valid JSON: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise DeploymentInvalid("release manifest has an unknown schema")

    required = {
        "schema_version", "commit", "branch", "source_root", "release_root",
        "snapshot_root", "runtime_fingerprint", "files", "launcher_identity",
        "created_at", "entrypoints", "payload_sha256",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise DeploymentInvalid(f"release manifest is missing fields: {', '.join(missing)}")
    payload_digest = payload.get("payload_sha256")
    if not isinstance(payload_digest, str) or not _HEX64.fullmatch(payload_digest):
        raise DeploymentInvalid("release manifest payload_sha256 is invalid")
    unsigned = {key: value for key, value in payload.items() if key != "payload_sha256"}
    if _sha256_bytes(_canonical_json(unsigned)) != payload_digest:
        raise DeploymentInvalid("release manifest payload_sha256 mismatch")
    if raw != _canonical_json(payload) + b"\n":
        raise DeploymentInvalid("release manifest is not canonical JSON")

    commit = payload.get("commit")
    runtime_fingerprint = payload.get("runtime_fingerprint")
    if not isinstance(commit, str) or not _HEX40.fullmatch(commit):
        raise DeploymentInvalid("release manifest commit is not a full lowercase Git object id")
    if not isinstance(runtime_fingerprint, str) or not _HEX64.fullmatch(runtime_fingerprint):
        raise DeploymentInvalid("release manifest runtime_fingerprint is invalid")
    if payload.get("branch") != branch:
        raise DeploymentInvalid(f"release manifest branch is not {branch}")

    source = source.resolve()
    source_root = _absolute_path(payload.get("source_root"), "source_root")
    release_root = _absolute_path(payload.get("release_root"), "release_root")
    snapshot_root = _absolute_path(payload.get("snapshot_root"), "snapshot_root")
    if source_root != source:
        raise DeploymentInvalid(
            f"release manifest source_root {source_root} does not match configured source {source}"
        )
    if not path.is_relative_to(release_root) or not snapshot_root.is_relative_to(release_root):
        raise DeploymentInvalid("release manifest and snapshot must remain inside release_root")
    if not snapshot_root.is_dir():
        raise DeploymentInvalid(f"release manifest snapshot_root is not a directory: {snapshot_root}")

    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise DeploymentInvalid("release manifest files must be a non-empty list")
    seen: set[str] = set()
    for record in files:
        if not isinstance(record, dict):
            raise DeploymentInvalid("release manifest file record is not an object")
        runtime_path = _safe_runtime_path(record.get("path"))
        if runtime_path in seen:
            raise DeploymentInvalid(f"release manifest repeats runtime path: {runtime_path}")
        seen.add(runtime_path)
        if record.get("git_mode") not in ("100644", "100755", "120000"):
            raise DeploymentInvalid(f"release manifest has invalid Git mode for {runtime_path}")
        blob_oid = record.get("blob_oid")
        file_sha = record.get("sha256")
        size = record.get("size")
        if not isinstance(blob_oid, str) or not (_HEX40.fullmatch(blob_oid) or _HEX64.fullmatch(blob_oid)):
            raise DeploymentInvalid(f"release manifest has invalid blob id for {runtime_path}")
        if not isinstance(file_sha, str) or not _HEX64.fullmatch(file_sha):
            raise DeploymentInvalid(f"release manifest has invalid SHA-256 for {runtime_path}")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise DeploymentInvalid(f"release manifest has invalid size for {runtime_path}")
    for required_path in ("scripts/brain_deploy.py", "scripts/brain_server.py"):
        if required_path not in seen:
            raise DeploymentInvalid(f"release manifest omits required runtime path {required_path}")

    launcher = payload.get("launcher_identity")
    if not isinstance(launcher, dict):
        raise DeploymentInvalid("release manifest launcher_identity is invalid")
    launcher_path = _absolute_path(launcher.get("path"), "launcher_identity.path")
    launcher_sha256 = launcher.get("sha256")
    if not isinstance(launcher_sha256, str) or not _HEX64.fullmatch(launcher_sha256):
        raise DeploymentInvalid("release manifest launcher_identity.sha256 is invalid")
    try:
        launcher_stat = launcher_path.lstat()
    except OSError as error:
        raise DeploymentInvalid(f"cannot inspect installed launcher {launcher_path}: {error}") from error
    if stat.S_ISLNK(launcher_stat.st_mode) or not stat.S_ISREG(launcher_stat.st_mode):
        raise DeploymentInvalid("installed launcher must be a regular, non-symlink file")
    observed_launcher_sha256 = _sha256_bytes(
        _read_bounded(launcher_path, MAX_MANIFEST_BYTES, "installed launcher")
    )
    if observed_launcher_sha256 != launcher_sha256:
        raise DeploymentInvalid(
            "installed launcher digest does not match the admitted release manifest"
        )

    entrypoints = payload.get("entrypoints")
    serve = entrypoints.get("serve") if isinstance(entrypoints, dict) else None
    if not isinstance(serve, dict):
        raise DeploymentInvalid("release manifest entrypoints.serve is invalid")
    source_path = _safe_runtime_path(serve.get("source_path"))
    if source_path != "scripts/brain_server.py":
        raise DeploymentInvalid("release manifest serve source_path is not brain_server.py")
    serve_cwd = _absolute_path(serve.get("cwd"), "entrypoints.serve.cwd")
    virtual_file = _absolute_path(serve.get("virtual_file"), "entrypoints.serve.virtual_file")
    if serve_cwd != source or virtual_file != source / source_path:
        raise DeploymentInvalid("release manifest does not preserve the canonical Brain cwd/root")
    serve_argv_value = serve.get("argv")
    if (
        not isinstance(serve_argv_value, list)
        or not serve_argv_value
        or any(not isinstance(item, str) or not item for item in serve_argv_value)
    ):
        raise DeploymentInvalid("release manifest serve argv is invalid")
    serve_argv = tuple(serve_argv_value)
    if (
        len(serve_argv) < 4
        or not Path(serve_argv[0]).is_absolute()
        or serve_argv[1] != "-I"
        or Path(serve_argv[2]).resolve() != launcher_path
    ):
        raise DeploymentInvalid("release manifest serve argv does not use the installed -I launcher")
    if serve_argv[3] != "serve":
        raise DeploymentInvalid("release manifest serve argv has the wrong launcher mode")
    state_root, selection_path = _validate_fixed_serve_argv(
        serve_argv, source, branch
    )
    deploy_state_path, deploy_service = _validate_deploy_entrypoint(
        entrypoints,
        source=source,
        branch=branch,
        launcher_path=launcher_path,
        interpreter=serve_argv[0],
        state_root=state_root,
        selection=selection_path,
    )

    if not isinstance(payload.get("created_at"), str) or not payload["created_at"]:
        raise DeploymentInvalid("release manifest created_at is invalid")
    return ReleaseManifest(
        path=path,
        manifest_sha256=actual_sha256,
        commit=commit,
        branch=branch,
        source_root=source_root,
        release_root=release_root,
        snapshot_root=snapshot_root,
        runtime_fingerprint=runtime_fingerprint,
        launcher_path=launcher_path,
        launcher_sha256=launcher_sha256,
        serve_cwd=serve_cwd,
        serve_argv=serve_argv,
        selection_path=selection_path,
        deploy_state_path=deploy_state_path,
        deploy_service=deploy_service,
        payload=payload,
    )


def _time_remaining(
    deadline: float, monotonic: Callable[[], float], label: str
) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise DeploymentDeferred(f"{label} deadline expired")
    return remaining


def _command_result(
    command: list[str],
    *,
    source: Path,
    runner: Runner,
    deadline: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "LC_ALL": "C",
        "SYSTEMD_PAGER": "cat",
        "SYSTEMD_COLORS": "0",
    }
    timeout = COMMAND_TIMEOUT_SECONDS
    if deadline is not None:
        timeout = min(timeout, _time_remaining(deadline, monotonic, "deployment"))
    try:
        result = runner(
            command,
            cwd=source,
            text=True,
            capture_output=True,
            check=False,
            timeout=max(0.01, timeout),
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise DeploymentDeferred(f"command timed out: {command[0]}") from error
    except OSError as error:
        raise DeploymentDeferred(f"cannot execute {command[0]}: {error}") from error
    if deadline is not None:
        _time_remaining(deadline, monotonic, "deployment")
    return result


def _command_output(
    command: list[str],
    *,
    source: Path,
    runner: Runner,
    label: str,
    deadline: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> str:
    result = _command_result(
        command, source=source, runner=runner, deadline=deadline, monotonic=monotonic
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise DeploymentDeferred(f"{label}: {detail[:500]}")
    return result.stdout


def _parse_properties(output: str, unit: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            raise DeploymentInvalid(f"systemd returned malformed properties for {unit}")
        key, value = line.split("=", 1)
        if not key or key in properties:
            raise DeploymentInvalid(f"systemd returned duplicate/empty property for {unit}")
        properties[key] = value
    return properties


def installed_unit_receipts(
    source: Path,
    service: str,
    runner: Runner,
    *,
    deadline: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, dict]:
    """Fingerprint installed bytes only while systemd says those bytes are applied."""
    units = (service, "brain-deploy.service", "brain-deploy.path")
    if len(set(units)) != len(units):
        raise DeploymentInvalid("managed unit names must be distinct")
    receipts: dict[str, dict] = {}
    for unit in units:
        output = _command_output(
            [
                "systemctl", "--user", "show", unit, "--no-pager",
                "--property=LoadState", "--property=NeedDaemonReload",
                "--property=FragmentPath", "--property=DropInPaths",
            ],
            source=source,
            runner=runner,
            label=f"cannot inspect applied definition for {unit}",
            deadline=deadline,
            monotonic=monotonic,
        )
        properties = _parse_properties(output, unit)
        if properties.get("LoadState") != "loaded" or not properties.get("FragmentPath"):
            raise DeploymentInvalid(f"{unit} has no loaded installed definition")
        if properties.get("NeedDaemonReload") != "no":
            raise DeploymentDeferred(
                f"{unit} has unapplied installed bytes; run systemctl --user daemon-reload"
            )
        rendered = _command_output(
            ["systemctl", "--user", "cat", unit, "--no-pager"],
            source=source,
            runner=runner,
            label=f"cannot read installed definition for {unit}",
            deadline=deadline,
            monotonic=monotonic,
        )
        receipts[unit] = {
            "properties": properties,
            "rendered_sha256": _sha256_bytes(rendered.encode("utf-8")),
        }
    return receipts


def deployment_fingerprint(manifest: ReleaseManifest, units: dict[str, dict]) -> str:
    applied = {
        "runtime_fingerprint": manifest.runtime_fingerprint,
        "launcher_identity": {
            "path": str(manifest.launcher_path),
            "sha256": manifest.launcher_sha256,
        },
        "installed_units": units,
    }
    return _sha256_bytes(_canonical_json(applied))


def read_state(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": STATE_SCHEMA_VERSION}
    raw = _read_bounded(path, 1024 * 1024, "deployment state")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DeploymentInvalid(f"deployment state is not valid JSON: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != STATE_SCHEMA_VERSION:
        raise DeploymentInvalid("deployment state has an unknown schema")
    fingerprint = payload.get("fingerprint")
    manifest_sha = payload.get("manifest_sha256")
    if (fingerprint is None) != (manifest_sha is None):
        raise DeploymentInvalid("deployment state has a partial applied identity")
    if fingerprint is not None:
        if not isinstance(fingerprint, str) or not _HEX64.fullmatch(fingerprint):
            raise DeploymentInvalid("deployment state fingerprint is invalid")
        if not isinstance(manifest_sha, str) or not _HEX64.fullmatch(manifest_sha):
            raise DeploymentInvalid("deployment state manifest_sha256 is invalid")
        applied = payload.get("applied")
        if not isinstance(applied, dict) or applied.get("fingerprint") != fingerprint:
            raise DeploymentInvalid("deployment state applied receipt is inconsistent")
    return payload


def _write_state(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
    except OSError as error:
        raise DeploymentInvalid(f"cannot prepare deployment state directory {path.parent}: {error}") from error
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary_name = temporary.name
            json.dump(payload, temporary, sort_keys=True, separators=(",", ":"))
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as error:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise DeploymentInvalid(f"cannot write deployment state {path}: {error}") from error


@contextmanager
def deployment_lock(path: Path):
    """A second, helper-state lock; the launcher owns the outer selection lock."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DeploymentDeferred("another deployment helper holds the state lock") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _service_observation(
    source: Path,
    service: str,
    runner: Runner,
    *,
    deadline: float | None = None,
    monotonic: Callable[[], float] = time.monotonic,
) -> ServiceObservation:
    output = _command_output(
        [
            "systemctl", "--user", "show", service, "--no-pager",
            "--property=ActiveState", "--property=SubState", "--property=MainPID",
            "--property=ExecMainStartTimestampMonotonic",
        ],
        source=source,
        runner=runner,
        label=f"cannot inspect {service}",
        deadline=deadline,
        monotonic=monotonic,
    )
    properties = _parse_properties(output, service)
    try:
        main_pid = int(properties["MainPID"])
        start_timestamp = int(properties["ExecMainStartTimestampMonotonic"])
    except (KeyError, TypeError, ValueError) as error:
        raise DeploymentInvalid(f"systemd returned invalid process identity for {service}") from error
    return ServiceObservation(
        active_state=properties.get("ActiveState", ""),
        sub_state=properties.get("SubState", ""),
        main_pid=main_pid,
        start_timestamp_monotonic=start_timestamp,
    )


def _read_proc(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as handle:
            value = handle.read(limit + 1)
    except OSError as error:
        raise ReadinessError(f"cannot read {path}: {error}") from error
    if len(value) > limit:
        raise ReadinessError(f"kernel observation exceeds byte limit: {path}")
    return value


def _readiness_remaining(deadline: float, monotonic: Callable[[], float]) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise ReadinessError("readiness deadline expired")
    return remaining


def _process_details(
    proc_root: Path,
    pid: int,
    deadline: float,
    monotonic: Callable[[], float],
) -> tuple[int, Path, tuple[str, ...]]:
    process = proc_root / str(pid)
    try:
        _readiness_remaining(deadline, monotonic)
        stat_line = _read_proc(process / "stat", 64 * 1024).decode("utf-8")
        close = stat_line.rfind(")")
        fields = stat_line[close + 2 :].split()
        start_ticks = int(fields[19])
        _readiness_remaining(deadline, monotonic)
        cwd = (process / "cwd").resolve(strict=True)
        _readiness_remaining(deadline, monotonic)
        raw_argv = _read_proc(process / "cmdline", 1024 * 1024)
        argv = tuple(item.decode("utf-8") for item in raw_argv.rstrip(b"\0").split(b"\0"))
    except (OSError, UnicodeDecodeError, ValueError, IndexError) as error:
        raise ReadinessError(f"cannot read process identity for MainPID {pid}: {error}") from error
    if close < 0 or start_ticks <= 0 or not argv or any(not item for item in argv):
        raise ReadinessError(f"process identity for MainPID {pid} is malformed")
    _readiness_remaining(deadline, monotonic)
    return start_ticks, cwd, argv


def _listening_inodes(
    proc_root: Path,
    port: int,
    deadline: float,
    monotonic: Callable[[], float],
) -> dict[int, set[str]]:
    listeners: dict[int, set[str]] = {}
    expected_port = f"{port:04X}"
    for table_name in ("tcp", "tcp6"):
        table = proc_root / "net" / table_name
        try:
            _readiness_remaining(deadline, monotonic)
            lines = _read_proc(table, MAX_PROC_FILE_BYTES).decode("ascii").splitlines()[1:]
        except UnicodeDecodeError as error:
            raise ReadinessError(f"cannot decode {table}") from error
        if len(lines) > MAX_PROC_ROWS:
            raise ReadinessError(f"too many socket rows in {table}")
        for line in lines:
            _readiness_remaining(deadline, monotonic)
            fields = line.split()
            if len(fields) < 10 or fields[3] != "0A":
                continue
            try:
                address, encoded_port = fields[1].rsplit(":", 1)
                inode = int(fields[9])
            except (ValueError, IndexError):
                raise ReadinessError(f"malformed listening socket row in {table}")
            if encoded_port.upper() == expected_port:
                listeners.setdefault(inode, set()).add(f"{table_name}:{address.upper()}")
    return listeners


def _socket_owners(
    proc_root: Path,
    inode: int,
    deadline: float,
    monotonic: Callable[[], float],
) -> set[int]:
    owners: set[int] = set()
    try:
        processes = proc_root.iterdir()
    except OSError as error:
        raise ReadinessError(f"cannot enumerate {proc_root}: {error}") from error
    process_count = 0
    descriptor_count = 0
    try:
        for process in processes:
            process_count += 1
            if process_count > MAX_PROC_ROWS:
                raise ReadinessError("process table exceeds observation limit")
            _readiness_remaining(deadline, monotonic)
            if not process.name.isdigit():
                continue
            try:
                descriptors = (process / "fd").iterdir()
                for descriptor in descriptors:
                    descriptor_count += 1
                    if descriptor_count > MAX_PROC_FDS:
                        raise ReadinessError(
                            "process descriptor scan exceeds observation limit"
                        )
                    _readiness_remaining(deadline, monotonic)
                    try:
                        target = os.readlink(descriptor)
                    except OSError:
                        continue
                    match = _SOCKET_LINK.fullmatch(target)
                    if match and int(match.group(1)) == inode:
                        owners.add(int(process.name))
            except OSError:
                continue
    except OSError as error:
        raise ReadinessError(f"cannot enumerate {proc_root}: {error}") from error
    return owners


def _owned_listener(
    proc_root: Path,
    pid: int,
    deadline: float,
    monotonic: Callable[[], float],
) -> int:
    listeners = _listening_inodes(
        proc_root, EXPECTED_PORT, deadline, monotonic
    )
    if len(listeners) != 1:
        raise ReadinessError(
            f"expected exactly one listener on port {EXPECTED_PORT}, observed {len(listeners)}"
        )
    inode, addresses = next(iter(listeners.items()))
    if "tcp:00000000" not in addresses:
        raise ReadinessError(
            f"port {EXPECTED_PORT} listener is not bound to {EXPECTED_HOST}"
        )
    owners = _socket_owners(proc_root, inode, deadline, monotonic)
    if pid not in owners:
        raise ReadinessError(
            f"port {EXPECTED_PORT} listener inode {inode} is not owned by MainPID {pid}"
        )
    other_owners = sorted(owners - {pid})
    if other_owners:
        raise ReadinessError(
            f"port {EXPECTED_PORT} listener is also held by PIDs {other_owners}"
        )
    return inode


def _identity(
    source: Path,
    service: str,
    manifest: ReleaseManifest,
    runner: Runner,
    proc_root: Path,
    before: ServiceObservation | None,
    deadline: float,
    monotonic: Callable[[], float],
) -> ServiceIdentity:
    _readiness_remaining(deadline, monotonic)
    observation = _service_observation(
        source, service, runner, deadline=deadline, monotonic=monotonic
    )
    if observation.active_state != "active" or observation.sub_state != "running":
        raise ReadinessError(
            f"{service} is not active/running ({observation.active_state}/{observation.sub_state})"
        )
    if observation.main_pid <= 0 or observation.start_timestamp_monotonic <= 0:
        raise ReadinessError(f"{service} has no live MainPID/start timestamp")
    if before is not None:
        if before.main_pid > 0 and observation.main_pid == before.main_pid:
            raise ReadinessError(f"{service} did not obtain a new MainPID after restart")
        if observation.start_timestamp_monotonic <= before.start_timestamp_monotonic:
            raise ReadinessError(f"{service} did not obtain a newer start timestamp after restart")
    start_ticks, cwd, argv = _process_details(
        proc_root, observation.main_pid, deadline, monotonic
    )
    if cwd != manifest.serve_cwd:
        raise ReadinessError(
            f"MainPID {observation.main_pid} cwd {cwd} does not match {manifest.serve_cwd}"
        )
    if argv != manifest.serve_argv:
        raise ReadinessError(f"MainPID {observation.main_pid} argv does not match release manifest")
    listener_inode = _owned_listener(
        proc_root, observation.main_pid, deadline, monotonic
    )
    return ServiceIdentity(
        main_pid=observation.main_pid,
        start_timestamp_monotonic=observation.start_timestamp_monotonic,
        process_start_ticks=start_ticks,
        cwd=str(cwd),
        argv=argv,
        listener_inode=listener_inode,
    )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _default_opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _api_object(
    opener,
    route: str,
    deadline: float,
    monotonic: Callable[[], float],
) -> dict:
    url = f"http://127.0.0.1:{EXPECTED_PORT}/api/{route}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Connection": "close"},
        method="GET",
    )
    try:
        remaining = _readiness_remaining(deadline, monotonic)
        with opener.open(
            request, timeout=max(0.01, min(API_TIMEOUT_SECONDS, remaining))
        ) as response:
            status_code = getattr(response, "status", 200)
            if status_code != 200:
                raise ReadinessError(f"Brain API {route} returned HTTP {status_code}")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except ReadinessError:
        raise
    except (OSError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as error:
        raise ReadinessError(f"Brain API {route} request failed: {type(error).__name__}") from error
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ReadinessError(f"Brain API {route} response exceeds {MAX_RESPONSE_BYTES} bytes")
    _readiness_remaining(deadline, monotonic)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReadinessError(f"Brain API {route} response is not JSON") from error
    if not isinstance(value, dict):
        raise ReadinessError(f"Brain API {route} response is not an object")
    return value


def _supported_apis(
    opener, deadline: float, monotonic: Callable[[], float]
) -> None:
    summary = _api_object(opener, "summary", deadline, monotonic)
    if not isinstance(summary.get("status_strip"), dict):
        raise ReadinessError("Brain API summary has an unsupported shape")
    operations = _api_object(opener, "operations", deadline, monotonic)
    server = operations.get("server")
    alive = server.get("alive") if isinstance(server, dict) else None
    if not (
        operations.get("read_only") is True
        and isinstance(alive, dict)
        and alive.get("value") is True
    ):
        raise ReadinessError("Brain API operations has an unsupported shape")


def wait_for_service(
    *,
    source: Path,
    service: str,
    manifest: ReleaseManifest,
    runner: Runner,
    opener,
    proc_root: Path,
    before: ServiceObservation | None,
    deadline: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> ServiceIdentity:
    last_reason = "no readiness observation"
    while True:
        if monotonic() >= deadline:
            raise DeploymentDeferred(f"Brain readiness failed: {last_reason}")
        try:
            first = _identity(
                source, service, manifest, runner, proc_root, before, deadline, monotonic
            )
            _supported_apis(opener, deadline, monotonic)
            second = _identity(
                source, service, manifest, runner, proc_root, before, deadline, monotonic
            )
            if second != first:
                raise ReadinessError("service identity changed during API readiness probes")
            _readiness_remaining(deadline, monotonic)
            return second
        except (ReadinessError, DeploymentDeferred) as error:
            last_reason = str(error)
        now = monotonic()
        if now >= deadline:
            raise DeploymentDeferred(f"Brain readiness failed: {last_reason}")
        sleep(min(READINESS_POLL_SECONDS, deadline - now))


def _attempt_receipt(status: str, fingerprint: str, manifest: ReleaseManifest, detail: str, started_at: str) -> dict:
    return {
        "status": status,
        "fingerprint": fingerprint,
        "manifest_sha256": manifest.manifest_sha256,
        "commit": manifest.commit,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "detail": detail[:500],
    }


def _record_failed_attempt(
    state_path: Path,
    old_state: dict,
    fingerprint: str,
    manifest: ReleaseManifest,
    detail: str,
    started_at: str,
) -> None:
    payload = dict(old_state)
    payload["schema_version"] = STATE_SCHEMA_VERSION
    payload["last_attempt"] = _attempt_receipt(
        "failed", fingerprint, manifest, detail, started_at
    )
    _write_state(state_path, payload)


def deploy(
    source: Path,
    state: Path,
    branch: str,
    service: str,
    release_manifest: Path,
    release_manifest_sha256: str,
    selection: Path,
    runner: Runner = subprocess.run,
    opener=None,
    proc_root: Path = Path("/proc"),
    readiness_timeout: float = READINESS_TIMEOUT_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> DeploymentResult:
    """Apply one admitted candidate; state becomes applied only after full proof."""
    source = source.resolve()
    state = state.resolve()
    selection = selection.resolve()
    transaction_deadline = monotonic() + TRANSACTION_TIMEOUT_SECONDS
    manifest = load_release_manifest(
        release_manifest, release_manifest_sha256, source, branch
    )
    if state != manifest.deploy_state_path:
        raise DeploymentInvalid(
            f"state {state} does not match the release manifest deploy entrypoint"
        )
    if service != manifest.deploy_service:
        raise DeploymentInvalid(
            f"service {service} does not match the release manifest deploy entrypoint"
        )
    if selection != manifest.selection_path:
        raise DeploymentInvalid(
            f"selection {selection} does not match the release manifest"
        )
    opener = opener or _default_opener()
    with deployment_lock(state.with_suffix(state.suffix + ".lock")):
        old_state = read_state(state)
        units_before = installed_unit_receipts(
            source,
            service,
            runner,
            deadline=transaction_deadline,
            monotonic=monotonic,
        )
        fingerprint = deployment_fingerprint(manifest, units_before)

        if old_state.get("fingerprint") == fingerprint:
            readiness_deadline = min(
                transaction_deadline, monotonic() + max(readiness_timeout, 0.01)
            )
            current = wait_for_service(
                source=source,
                service=service,
                manifest=manifest,
                runner=runner,
                opener=opener,
                proc_root=proc_root,
                before=None,
                deadline=readiness_deadline,
                monotonic=monotonic,
                sleep=sleep,
            )
            return DeploymentResult(
                "unchanged",
                "applied runtime and installed identities are unchanged; current service qualified",
                fingerprint,
                current,
            )

        before = _service_observation(
            source,
            service,
            runner,
            deadline=transaction_deadline,
            monotonic=monotonic,
        )
        started_at = _utc_now()
        restart = _command_result(
            ["systemctl", "--user", "restart", service],
            source=source,
            runner=runner,
            deadline=transaction_deadline,
            monotonic=monotonic,
        )
        if restart.returncode != 0:
            detail = (restart.stderr or restart.stdout or "restart failed").strip()
            error = DeploymentDeferred(f"cannot restart {service}: {detail[:500]}")
            _record_failed_attempt(state, old_state, fingerprint, manifest, str(error), started_at)
            raise error
        try:
            readiness_deadline = min(
                transaction_deadline, monotonic() + max(readiness_timeout, 0.01)
            )
            identity = wait_for_service(
                source=source,
                service=service,
                manifest=manifest,
                runner=runner,
                opener=opener,
                proc_root=proc_root,
                before=before,
                deadline=readiness_deadline,
                monotonic=monotonic,
                sleep=sleep,
            )
            manifest_after = load_release_manifest(
                release_manifest, release_manifest_sha256, source, branch
            )
            _readiness_remaining(readiness_deadline, monotonic)
            units_after = installed_unit_receipts(
                source,
                service,
                runner,
                deadline=readiness_deadline,
                monotonic=monotonic,
            )
            if manifest_after != manifest:
                raise DeploymentDeferred("release manifest identity changed during restart")
            if units_after != units_before:
                raise DeploymentDeferred("installed unit identity changed during restart")
            final_identity = _identity(
                source,
                service,
                manifest,
                runner,
                proc_root,
                before,
                readiness_deadline,
                monotonic,
            )
            if final_identity != identity:
                raise DeploymentDeferred(
                    "service identity changed after installed-unit verification"
                )
            _readiness_remaining(readiness_deadline, monotonic)
        except ReadinessError as observation_error:
            error = DeploymentDeferred(f"Brain readiness failed: {observation_error}")
            _record_failed_attempt(state, old_state, fingerprint, manifest, str(error), started_at)
            raise error from observation_error
        except DeploymentError as error:
            _record_failed_attempt(state, old_state, fingerprint, manifest, str(error), started_at)
            raise

        success_attempt = _attempt_receipt(
            "succeeded", fingerprint, manifest, "new service identity and APIs qualified", started_at
        )
        applied = {
            "fingerprint": fingerprint,
            "manifest_sha256": manifest.manifest_sha256,
            "commit": manifest.commit,
            "runtime_fingerprint": manifest.runtime_fingerprint,
            "launcher_identity": {
                "path": str(manifest.launcher_path),
                "sha256": manifest.launcher_sha256,
            },
            "installed_units": units_after,
            "service": asdict(identity),
            "recorded_at": _utc_now(),
        }
        new_state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "fingerprint": fingerprint,
            # The launcher reads this top-level key before promoting candidate.
            "manifest_sha256": manifest.manifest_sha256,
            "applied": applied,
            "last_attempt": success_attempt,
        }
        _write_state(state, new_state)
        return DeploymentResult(
            "restarted", "service restarted and bound to the admitted release", fingerprint, identity
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--service", default="brain.service")
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--release-manifest-sha256", required=True)
    parser.add_argument("--selection", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        result = deploy(
            source=arguments.source,
            state=arguments.state,
            branch=arguments.branch,
            service=arguments.service,
            release_manifest=arguments.release_manifest,
            release_manifest_sha256=arguments.release_manifest_sha256,
            selection=arguments.selection,
        )
    except DeploymentInvalid as error:
        print(json.dumps({"status": "invalid", "detail": str(error)}, sort_keys=True))
        return EXIT_INVALID
    except DeploymentDeferred as error:
        print(json.dumps({"status": "deferred", "detail": str(error)}, sort_keys=True))
        return EXIT_DEFERRED
    except DeploymentError as error:
        print(json.dumps({"status": "error", "detail": str(error)}, sort_keys=True))
        return 1
    output = {
        "status": result.status,
        "detail": result.detail,
        "fingerprint": result.fingerprint,
        "service": asdict(result.service) if result.service else None,
    }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
