#!/usr/bin/python3 -I
"""Admit and execute immutable Brain releases without importing checkout code.

This file is installed separately and invoked with ``/usr/bin/python3 -I`` by
both Brain units.  Before admission it imports only the Python standard library
and invokes read-only Git plumbing.  Repository Python is compiled from verified
raw blobs under its canonical virtual filename; repository-local imports and
Python child scripts resolve only through the same verified release.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import fcntl
import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator


SCHEMA_VERSION = 1
EXIT_DEFERRED = 20
EXIT_INTEGRITY = 21
EXIT_INTERFACE = 22
GIT = "/usr/bin/git"
COMMAND_TIMEOUT_SECONDS = 20
MAX_GIT_OUTPUT = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
RUNTIME_PATHS = ("scripts", "memory/brain/view")
DIRTY_GUARD_PATHS = (
    ".gitignore",
    ".gitattributes",
    "scripts",
    "memory/brain/view",
    "systemd/libexec/brain-launch.py",
    "systemd/user",
)
LAUNCHER_TEMPLATE = "systemd/libexec/brain-launch.py"
ENTRYPOINT_DEPLOY = "scripts/brain_deploy.py"
ENTRYPOINT_SERVE = "scripts/brain_server.py"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
ENV_MANIFEST = "BRAIN_LAUNCH_MANIFEST"
ENV_MANIFEST_SHA = "BRAIN_LAUNCH_MANIFEST_SHA256"
ENV_SOURCE = "BRAIN_LAUNCH_SOURCE_ROOT"
ENV_BRANCH = "BRAIN_LAUNCH_BRANCH"
ENV_STATE = "BRAIN_LAUNCH_STATE_ROOT"
ENV_SELECTION = "BRAIN_LAUNCH_SELECTION"
ENV_HELPER_STATE = "BRAIN_LAUNCH_HELPER_STATE"
ENV_SERVICE = "BRAIN_LAUNCH_SERVICE"
ENV_HOST = "BRAIN_LAUNCH_HOST"
ENV_PORT = "BRAIN_LAUNCH_PORT"


class LaunchError(RuntimeError):
    exit_code = 1


class AdmissionDeferred(LaunchError):
    exit_code = EXIT_DEFERRED


class IntegrityError(LaunchError):
    exit_code = EXIT_INTEGRITY


class InterfaceError(LaunchError):
    exit_code = EXIT_INTERFACE


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InterfaceError(message)


@dataclasses.dataclass(frozen=True)
class FileRecord:
    path: str
    git_mode: str
    blob_oid: str
    sha256: str
    size: int
    raw: bytes = dataclasses.field(compare=False, repr=False)

    def manifest_value(self) -> dict[str, object]:
        return {
            "path": self.path,
            "git_mode": self.git_mode,
            "blob_oid": self.blob_oid,
            "sha256": self.sha256,
            "size": self.size,
        }


@dataclasses.dataclass(frozen=True)
class Admission:
    source_root: Path
    branch: str
    commit: str
    runtime_fingerprint: str
    files: tuple[FileRecord, ...]


@dataclasses.dataclass(frozen=True)
class Config:
    source_root: Path
    branch: str
    state_root: Path
    selection: Path
    helper_state: Path
    service: str
    host: str
    port: int
    launcher_path: Path
    launcher_sha256: str
    interpreter_token: str


@dataclasses.dataclass(frozen=True)
class Release:
    manifest_path: Path
    manifest_sha256: str
    manifest: dict[str, object]
    sources: dict[str, bytes]

    @property
    def reference(self) -> dict[str, str]:
        return {
            "manifest_path": str(self.manifest_path),
            "manifest_sha256": self.manifest_sha256,
        }


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _regular_bytes(path: Path, *, limit: int | None = None,
                   error_type: type[LaunchError] = IntegrityError) -> bytes:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise error_type(f"not a regular file: {path}")
        if limit is not None and info.st_size > limit:
            raise error_type(f"file exceeds byte limit: {path}")
        return path.read_bytes()
    except LaunchError:
        raise
    except OSError as error:
        raise error_type(f"cannot read {path}: {type(error).__name__}") from error


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _ensure_private_directory(path: Path) -> Path:
    path = path.expanduser().resolve()
    try:
        path.mkdir(parents=True, mode=0o700, exist_ok=True)
        info = path.lstat()
    except OSError as error:
        raise InterfaceError(f"cannot create private state root {path}: {type(error).__name__}") from error
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or (stat.S_IMODE(info.st_mode) & 0o077):
        raise InterfaceError(f"state root is not a private owner-only directory: {path}")
    return path


def _git_environment() -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
    }


def _git_result(source: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            [
                GIT,
                "--literal-pathspecs",
                "-c", "core.fsmonitor=false",
                "-c", "core.hooksPath=/dev/null",
                "-c", "core.attributesFile=/dev/null",
                "-c", "core.excludesFile=/dev/null",
                "-c", "diff.external=",
                "-c", "submodule.recurse=false",
                "-C", str(source),
                *arguments,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
            env=_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AdmissionDeferred(f"Git inspection failed: {type(error).__name__}") from error
    if len(result.stdout) > MAX_GIT_OUTPUT or len(result.stderr) > MAX_GIT_OUTPUT:
        raise AdmissionDeferred("Git inspection exceeded its byte limit")
    return result


def _git_bytes(source: Path, *arguments: str) -> bytes:
    result = _git_result(source, *arguments)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or "command failed"
        raise AdmissionDeferred(f"Git inspection failed: {detail}")
    return result.stdout


def _git_text(source: Path, *arguments: str) -> str:
    try:
        return _git_bytes(source, *arguments).decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise AdmissionDeferred("Git inspection returned a non-UTF-8 identity") from error


def _safe_relative(raw: bytes) -> str:
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AdmissionDeferred("runtime tree contains a non-UTF-8 path") from error
    pure = PurePosixPath(value)
    if (not value or value.startswith("/") or ".." in pure.parts
            or str(pure) != value or "\x00" in value):
        raise AdmissionDeferred(f"runtime tree contains an unsafe path: {value!r}")
    return value


def _parse_tree(source: Path, commit: str, paths: tuple[str, ...]) -> tuple[FileRecord, ...]:
    output = _git_bytes(source, "ls-tree", "-r", "-z", "--full-tree", commit, "--", *paths)
    records: list[FileRecord] = []
    seen: set[str] = set()
    for item in output.split(b"\0"):
        if not item:
            continue
        try:
            metadata, raw_path = item.split(b"\t", 1)
            mode, kind, raw_oid = metadata.split(b" ", 2)
            mode_text = mode.decode("ascii")
            kind_text = kind.decode("ascii")
            oid = raw_oid.decode("ascii")
        except (ValueError, UnicodeDecodeError) as error:
            raise AdmissionDeferred("runtime tree has malformed metadata") from error
        path = _safe_relative(raw_path)
        if kind_text != "blob" or mode_text not in ("100644", "100755"):
            raise AdmissionDeferred(f"runtime path is not a regular Git blob: {path}")
        if path in seen:
            raise AdmissionDeferred(f"runtime tree repeats path: {path}")
        seen.add(path)
        raw = _git_bytes(source, "cat-file", "blob", oid)
        records.append(FileRecord(path, mode_text, oid, _sha256(raw), len(raw), raw))
    records.sort(key=lambda record: record.path)
    if not records:
        raise AdmissionDeferred("no committed runtime source files")
    return tuple(records)


def _runtime_fingerprint(records: tuple[FileRecord, ...]) -> str:
    digest = hashlib.sha256()
    for record in records:
        for value in (record.path, record.git_mode, record.blob_oid, record.sha256, str(record.size)):
            digest.update(value.encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()


def _single_blob(source: Path, commit: str, relative: str) -> bytes:
    output = _git_bytes(source, "ls-tree", "-z", commit, "--", relative)
    items = [item for item in output.split(b"\0") if item]
    if len(items) != 1:
        raise AdmissionDeferred(f"required committed path is absent: {relative}")
    try:
        metadata, raw_path = items[0].split(b"\t", 1)
        mode, kind, raw_oid = metadata.split(b" ", 2)
    except ValueError as error:
        raise AdmissionDeferred(f"required committed path is malformed: {relative}") from error
    if _safe_relative(raw_path) != relative or kind != b"blob" or mode not in (b"100644", b"100755"):
        raise AdmissionDeferred(f"required committed path is not a regular blob: {relative}")
    return _git_bytes(source, "cat-file", "blob", raw_oid.decode("ascii"))


def _index_signature(source: Path) -> tuple[tuple[bytes, bytes, bytes, bytes], ...]:
    output = _git_bytes(source, "ls-files", "--stage", "-z")
    entries: list[tuple[bytes, bytes, bytes, bytes]] = []
    for item in output.split(b"\0"):
        if not item:
            continue
        try:
            metadata, path = item.split(b"\t", 1)
            mode, oid, stage = metadata.split(b" ", 2)
        except ValueError as error:
            raise AdmissionDeferred("Git index has malformed stage metadata") from error
        entries.append((path, mode, oid, stage))
    entries.sort()
    return tuple(entries)


def _head_signature(source: Path, commit: str) -> tuple[tuple[bytes, bytes, bytes, bytes], ...]:
    output = _git_bytes(source, "ls-tree", "-r", "-z", "--full-tree", commit)
    entries: list[tuple[bytes, bytes, bytes, bytes]] = []
    for item in output.split(b"\0"):
        if not item:
            continue
        try:
            metadata, path = item.split(b"\t", 1)
            mode, _kind, oid = metadata.split(b" ", 2)
        except ValueError as error:
            raise AdmissionDeferred("HEAD tree has malformed metadata") from error
        entries.append((path, mode, oid, b"0"))
    entries.sort()
    return tuple(entries)


def _untracked_runtime_paths(source: Path) -> tuple[str, ...]:
    # Preserve deliberately ignored generated view projections, matching the
    # established deployment semantics.  Ignore rules themselves are pinned raw
    # below, and every ignored file under executable/template roots is separately
    # enumerated so an ignore rule cannot hide Python or unit dirt.
    ordinary = _git_bytes(
        source, "ls-files", "--others", "--exclude-standard", "-z", "--",
        *DIRTY_GUARD_PATHS,
    )
    executable_all = _git_bytes(
        source, "ls-files", "--others", "-z", "--",
        ".gitignore", ".gitattributes", "scripts", "systemd",
    )
    found: set[str] = set()
    for raw_path in ordinary.split(b"\0"):
        if raw_path:
            found.add(_safe_relative(raw_path))
    for raw_path in executable_all.split(b"\0"):
        if not raw_path:
            continue
        path = _safe_relative(raw_path)
        pure = PurePosixPath(path)
        if "__pycache__" in pure.parts and pure.suffix == ".pyc":
            continue
        found.add(path)
    return tuple(sorted(found))


def _admit_source(config: Config) -> Admission:
    source = config.source_root
    top = Path(_git_text(source, "rev-parse", "--show-toplevel")).resolve()
    if top != source:
        raise AdmissionDeferred(f"source is not its Git top level: {top}")
    lock_path_text = _git_text(source, "rev-parse", "--git-path", "index.lock")
    lock_path = Path(lock_path_text)
    if not lock_path.is_absolute():
        lock_path = source / lock_path
    if os.path.lexists(lock_path):
        raise AdmissionDeferred(f"Git index is busy: {lock_path}")
    symbolic = _git_result(source, "symbolic-ref", "--quiet", "--short", "HEAD")
    if symbolic.returncode != 0:
        raise AdmissionDeferred(f"checked-out branch is not {config.branch}")
    try:
        checked_out = symbolic.stdout.decode("utf-8").strip()
    except UnicodeDecodeError as error:
        raise AdmissionDeferred("checked-out branch has a non-UTF-8 name") from error
    if checked_out != config.branch:
        raise AdmissionDeferred(f"checked-out branch is not {config.branch}")
    head = _git_text(source, "rev-parse", "--verify", "HEAD^{commit}")
    branch_commit = _git_text(
        source, "rev-parse", "--verify", f"refs/heads/{config.branch}^{{commit}}",
    )
    if not COMMIT_RE.fullmatch(head) or head != branch_commit:
        raise AdmissionDeferred("HEAD does not match the requested local branch")
    if _index_signature(source) != _head_signature(source, head):
        raise AdmissionDeferred("Git index has staged changes")
    if _untracked_runtime_paths(source):
        raise AdmissionDeferred("runtime source has uncommitted or untracked changes")

    guarded_records = _parse_tree(source, head, DIRTY_GUARD_PATHS)
    for record in guarded_records:
        checkout_path = source.joinpath(*PurePosixPath(record.path).parts)
        working = _regular_bytes(
            checkout_path, limit=MAX_GIT_OUTPUT, error_type=AdmissionDeferred,
        )
        if len(working) != record.size or _sha256(working) != record.sha256:
            raise AdmissionDeferred(f"runtime working bytes do not match raw Git blob: {record.path}")
    records = tuple(
        record for record in guarded_records
        if any(record.path == root or record.path.startswith(root + "/") for root in RUNTIME_PATHS)
    )
    if not records:
        raise AdmissionDeferred("no committed runtime source files")
    paths = {record.path for record in records}
    for required in (ENTRYPOINT_DEPLOY, ENTRYPOINT_SERVE):
        if required not in paths:
            raise AdmissionDeferred(f"required runtime entrypoint is absent: {required}")

    committed_launcher = _single_blob(source, head, LAUNCHER_TEMPLATE)
    if _sha256(committed_launcher) != config.launcher_sha256:
        raise AdmissionDeferred("installed launcher does not match the committed launcher template")
    return Admission(source, config.branch, head, _runtime_fingerprint(records), records)


def _interpreter_token() -> str:
    token = sys.orig_argv[0] if getattr(sys, "orig_argv", None) else sys.executable
    path = Path(token)
    if not path.is_absolute():
        raise InterfaceError("interpreter argv token must be absolute")
    return str(path)


def _config(arguments: argparse.Namespace) -> Config:
    if sys.flags.isolated != 1:
        raise InterfaceError("launcher requires an isolated Python interpreter (-I)")
    source = arguments.source.expanduser().resolve()
    try:
        source_info = source.lstat()
    except OSError as error:
        raise InterfaceError(f"cannot inspect source root {source}: {type(error).__name__}") from error
    if not stat.S_ISDIR(source_info.st_mode):
        raise InterfaceError(f"source root is not a directory: {source}")
    if not BRANCH_RE.fullmatch(arguments.branch) or ".." in arguments.branch.split("/"):
        raise InterfaceError("branch has an unsupported name")
    state_root = _ensure_private_directory(arguments.state_root)
    if _is_within(state_root, source) or _is_within(source, state_root):
        raise InterfaceError("state root and source root must be separate")
    selection = (arguments.selection or state_root / "selected-release.json").expanduser().resolve()
    helper_state = (arguments.helper_state or state_root / "brain-deploy-state.json").expanduser().resolve()
    for label, path in (("selection", selection), ("helper state", helper_state)):
        if not _is_within(path, state_root) or path == state_root:
            raise InterfaceError(f"{label} must be a file beneath the state root")
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+\.service", arguments.service):
        raise InterfaceError("service has an unsupported name")
    if not (1 <= arguments.port <= 65535):
        raise InterfaceError("port must be between 1 and 65535")
    launcher_path = Path(__file__).absolute()
    try:
        launcher_path = launcher_path.resolve(strict=True)
    except OSError as error:
        raise InterfaceError(f"cannot resolve installed launcher: {type(error).__name__}") from error
    if _is_within(launcher_path, source):
        raise InterfaceError("launcher must be installed outside the mutable source checkout")
    launcher_raw = _regular_bytes(launcher_path, limit=MAX_MANIFEST_BYTES, error_type=InterfaceError)
    return Config(
        source, arguments.branch, state_root, selection, helper_state,
        arguments.service, arguments.host, arguments.port,
        launcher_path, _sha256(launcher_raw), _interpreter_token(),
    )


def _entrypoints(config: Config) -> dict[str, object]:
    common = [
        "--source", str(config.source_root),
        "--branch", config.branch,
        "--state-root", str(config.state_root),
        "--selection", str(config.selection),
    ]
    prefix = [config.interpreter_token, "-I", str(config.launcher_path)]
    return {
        "deploy": {
            "source_path": ENTRYPOINT_DEPLOY,
            "virtual_file": str(config.source_root / ENTRYPOINT_DEPLOY),
            "cwd": str(config.source_root),
            "argv": prefix + ["deploy", *common, "--helper-state", str(config.helper_state),
                              "--service", config.service],
        },
        "serve": {
            "source_path": ENTRYPOINT_SERVE,
            "virtual_file": str(config.source_root / ENTRYPOINT_SERVE),
            "cwd": str(config.source_root),
            "argv": prefix + ["serve", *common, "--host", config.host,
                              "--port", str(config.port)],
        },
    }


def _manifest_payload(config: Config, admission: Admission, release_root: Path,
                      created_at: str) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "commit": admission.commit,
        "branch": admission.branch,
        "source_root": str(admission.source_root),
        "release_root": str(release_root),
        "snapshot_root": str(release_root / "snapshot"),
        "runtime_fingerprint": admission.runtime_fingerprint,
        "files": [record.manifest_value() for record in admission.files],
        "launcher_identity": {
            "path": str(config.launcher_path),
            "sha256": config.launcher_sha256,
        },
        "created_at": created_at,
        "entrypoints": _entrypoints(config),
    }


def _descriptor(release: Release) -> dict[str, object]:
    manifest = release.manifest
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_path": str(release.manifest_path),
        "manifest_sha256": release.manifest_sha256,
        "commit": manifest["commit"],
        "runtime_fingerprint": manifest["runtime_fingerprint"],
        "source_root": manifest["source_root"],
        "snapshot_root": manifest["snapshot_root"],
        "launcher_identity": manifest["launcher_identity"],
        "entrypoints": manifest["entrypoints"],
    }


def _write_new_file(path: Path, raw: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _freeze_tree(root: Path) -> None:
    files: list[Path] = []
    directories: list[Path] = []
    for current, names, filenames in os.walk(root, topdown=False, followlinks=False):
        current_path = Path(current)
        directories.append(current_path)
        for name in filenames:
            files.append(current_path / name)
        for name in names:
            child = current_path / name
            if child.is_symlink():
                raise IntegrityError(f"release contains a symlink: {child}")
    for path in files:
        path.chmod(0o400)
    for path in directories:
        path.chmod(0o500)


def _release_id(config: Config, admission: Admission) -> str:
    seed = {
        "commit": admission.commit,
        "runtime_fingerprint": admission.runtime_fingerprint,
        "source_root": str(admission.source_root),
        "launcher_identity": {"path": str(config.launcher_path), "sha256": config.launcher_sha256},
        "entrypoints": _entrypoints(config),
    }
    return _sha256(_canonical_json(seed))


def _prepare_release(config: Config) -> Release:
    first = _admit_source(config)
    releases = config.state_root / "releases"
    releases.mkdir(mode=0o700, exist_ok=True)
    release_root = releases / _release_id(config, first)
    manifest_path = release_root / "manifest.json"
    if release_root.exists():
        manifest_raw = _regular_bytes(manifest_path, limit=MAX_MANIFEST_BYTES)
        return _verify_release(config, manifest_path, _sha256(manifest_raw))

    temporary = Path(tempfile.mkdtemp(prefix=".prepare-", dir=releases))
    try:
        snapshot = temporary / "snapshot"
        snapshot.mkdir(mode=0o700)
        for record in first.files:
            target = snapshot.joinpath(*PurePosixPath(record.path).parts)
            target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            _write_new_file(target, record.raw, 0o600)
        created_at = datetime.now(timezone.utc).isoformat()
        payload = _manifest_payload(config, first, release_root, created_at)
        manifest = dict(payload)
        manifest["payload_sha256"] = _sha256(_canonical_json(payload))
        manifest_raw = _canonical_json(manifest) + b"\n"
        _write_new_file(temporary / "manifest.json", manifest_raw, 0o600)

        second = _admit_source(config)
        if second != first:
            raise AdmissionDeferred("source changed while the immutable release was prepared")
        _freeze_tree(temporary)
        try:
            os.rename(temporary, release_root)
        except FileExistsError:
            temporary.chmod(0o700)
            shutil.rmtree(temporary)
        _fsync_directory(releases)
    except Exception:
        if temporary.exists():
            for current, names, filenames in os.walk(temporary, topdown=False):
                for filename in filenames:
                    with contextlib.suppress(OSError):
                        (Path(current) / filename).chmod(0o600)
                for name in names:
                    with contextlib.suppress(OSError):
                        (Path(current) / name).chmod(0o700)
            with contextlib.suppress(OSError):
                temporary.chmod(0o700)
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    return _verify_release(config, manifest_path, _sha256(_regular_bytes(manifest_path)))


def _manifest_file_records(value: object) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or not value:
        raise IntegrityError("manifest files must be a non-empty list")
    records: list[dict[str, object]] = []
    previous = ""
    for item in value:
        if not isinstance(item, dict) or set(item) != {"path", "git_mode", "blob_oid", "sha256", "size"}:
            raise IntegrityError("manifest file record has an unsupported shape")
        path = item.get("path")
        try:
            safe_path = _safe_relative(path.encode("utf-8")) if isinstance(path, str) else None
        except (AdmissionDeferred, UnicodeEncodeError) as error:
            raise IntegrityError("manifest file path is unsafe") from error
        if not isinstance(path, str) or safe_path != path or path <= previous:
            raise IntegrityError("manifest file paths are unsafe or unordered")
        if item.get("git_mode") not in ("100644", "100755"):
            raise IntegrityError(f"manifest file has unsupported mode: {path}")
        if not isinstance(item.get("blob_oid"), str) or not re.fullmatch(r"[0-9a-f]{40,64}", item["blob_oid"]):
            raise IntegrityError(f"manifest file has invalid blob oid: {path}")
        if not isinstance(item.get("sha256"), str) or not SHA256_RE.fullmatch(item["sha256"]):
            raise IntegrityError(f"manifest file has invalid sha256: {path}")
        if not isinstance(item.get("size"), int) or item["size"] < 0 or item["size"] > MAX_GIT_OUTPUT:
            raise IntegrityError(f"manifest file has invalid size: {path}")
        records.append(item)
        previous = path
    return tuple(records)


def _load_manifest(manifest_path: Path, expected_sha256: str) -> tuple[dict[str, object], bytes]:
    if not SHA256_RE.fullmatch(expected_sha256):
        raise IntegrityError("release reference has an invalid manifest sha256")
    raw = _regular_bytes(manifest_path, limit=MAX_MANIFEST_BYTES)
    if _sha256(raw) != expected_sha256:
        raise IntegrityError("release manifest bytes do not match the selected sha256")
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntegrityError("release manifest is not valid JSON") from error
    if not isinstance(manifest, dict):
        raise IntegrityError("release manifest is not an object")
    payload_sha = manifest.get("payload_sha256")
    if not isinstance(payload_sha, str) or not SHA256_RE.fullmatch(payload_sha):
        raise IntegrityError("release manifest has no valid payload sha256")
    payload = dict(manifest)
    del payload["payload_sha256"]
    if _sha256(_canonical_json(payload)) != payload_sha:
        raise IntegrityError("release manifest payload sha256 does not verify")
    return manifest, raw


def _verify_frozen_release(release_root: Path) -> None:
    try:
        release_info = release_root.lstat()
    except OSError as error:
        raise IntegrityError(f"cannot inspect immutable release: {type(error).__name__}") from error
    if (not stat.S_ISDIR(release_info.st_mode) or release_info.st_uid != os.geteuid()
            or (stat.S_IMODE(release_info.st_mode) & 0o277)):
        raise IntegrityError("release root is not an owner-only non-writable directory")
    for current, names, filenames in os.walk(release_root, followlinks=False):
        current_path = Path(current)
        info = current_path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or (stat.S_IMODE(info.st_mode) & 0o277)):
            raise IntegrityError(f"release directory is not frozen: {current_path}")
        for name in [*names, *filenames]:
            path = current_path / name
            child = path.lstat()
            if child.st_uid != os.geteuid() or stat.S_ISLNK(child.st_mode):
                raise IntegrityError(f"release path has unsafe ownership or type: {path}")
            if stat.S_ISREG(child.st_mode) and (stat.S_IMODE(child.st_mode) & 0o277):
                raise IntegrityError(f"release file is not frozen: {path}")


def _verify_release(config: Config, manifest_path: Path, expected_sha256: str) -> Release:
    manifest_path = manifest_path.expanduser().resolve()
    if not _is_within(manifest_path, config.state_root / "releases"):
        raise IntegrityError("release manifest is outside the private release root")
    _verify_frozen_release(manifest_path.parent)
    manifest, _raw = _load_manifest(manifest_path, expected_sha256)
    identity = manifest.get("launcher_identity")
    expected_identity = {"path": str(config.launcher_path), "sha256": config.launcher_sha256}
    if identity != expected_identity:
        raise IntegrityError("installed launcher identity does not match the selected release")
    required_scalars = {
        "schema_version": SCHEMA_VERSION,
        "branch": config.branch,
        "source_root": str(config.source_root),
        "release_root": str(manifest_path.parent),
        "snapshot_root": str(manifest_path.parent / "snapshot"),
        "entrypoints": _entrypoints(config),
    }
    for key, expected in required_scalars.items():
        if manifest.get(key) != expected:
            raise IntegrityError(f"release manifest {key} does not match the launcher configuration")
    commit = manifest.get("commit")
    fingerprint = manifest.get("runtime_fingerprint")
    if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
        raise IntegrityError("release manifest commit is invalid")
    if not isinstance(fingerprint, str) or not SHA256_RE.fullmatch(fingerprint):
        raise IntegrityError("release manifest runtime fingerprint is invalid")
    recorded = _manifest_file_records(manifest.get("files"))

    current = _admit_source(config)
    if current.runtime_fingerprint != fingerprint:
        raise AdmissionDeferred("selected release does not match current clean runtime bytes")
    try:
        old_records = _parse_tree(config.source_root, commit, RUNTIME_PATHS)
    except AdmissionDeferred as error:
        raise IntegrityError("release manifest pinned Git tree cannot be verified") from error
    expected_records = tuple(record.manifest_value() for record in old_records)
    if recorded != expected_records or _runtime_fingerprint(old_records) != fingerprint:
        raise IntegrityError("release manifest does not match its pinned raw Git tree")

    snapshot_root = manifest_path.parent / "snapshot"
    sources: dict[str, bytes] = {}
    for item, git_record in zip(recorded, old_records, strict=True):
        relative = str(item["path"])
        snapshot_path = snapshot_root.joinpath(*PurePosixPath(relative).parts)
        snapshot_raw = _regular_bytes(snapshot_path, limit=MAX_GIT_OUTPUT)
        if (len(snapshot_raw) != item["size"] or _sha256(snapshot_raw) != item["sha256"]
                or snapshot_raw != git_record.raw):
            raise IntegrityError(f"release snapshot bytes do not verify: {relative}")
        if relative.startswith("scripts/") and relative.endswith(".py"):
            sources[relative] = snapshot_raw
    for required in (ENTRYPOINT_DEPLOY, ENTRYPOINT_SERVE):
        if required not in sources:
            raise IntegrityError(f"release snapshot lacks entrypoint: {required}")
    return Release(manifest_path, expected_sha256, manifest, sources)


def _validate_release_reference(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"manifest_path", "manifest_sha256"}:
        raise IntegrityError("selector release reference has an unsupported shape")
    path, digest = value.get("manifest_path"), value.get("manifest_sha256")
    if not isinstance(path, str) or not path.startswith("/"):
        raise IntegrityError("selector manifest path is not absolute")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        raise IntegrityError("selector manifest sha256 is invalid")
    return {"manifest_path": path, "manifest_sha256": digest}


def _read_selector(config: Config) -> dict[str, object]:
    if not config.selection.exists():
        return {"schema_version": SCHEMA_VERSION, "active": None, "candidate": None}
    raw = _regular_bytes(config.selection, limit=65_536)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntegrityError("release selector is not valid JSON") from error
    if not isinstance(value, dict) or set(value) != {"schema_version", "active", "candidate"}:
        raise IntegrityError("release selector has an unsupported shape")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise IntegrityError("release selector schema is unsupported")
    return {
        "schema_version": SCHEMA_VERSION,
        "active": _validate_release_reference(value.get("active")),
        "candidate": _validate_release_reference(value.get("candidate")),
    }


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    raw = _canonical_json(value) + b"\n"
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.fchmod(descriptor, 0o600)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary_name, path)
        _fsync_directory(path.parent)
    except OSError as error:
        if temporary_name:
            with contextlib.suppress(OSError):
                Path(temporary_name).unlink()
        raise IntegrityError(f"cannot update private selector {path}: {type(error).__name__}") from error


@contextlib.contextmanager
def _deploy_lock(config: Config) -> Iterator[None]:
    lock_path = config.state_root / "launcher.lock"
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise IntegrityError(f"cannot open launcher lock: {type(error).__name__}") from error
    try:
        info = os.fstat(descriptor)
        if info.st_uid != os.geteuid() or not stat.S_ISREG(info.st_mode) or (stat.S_IMODE(info.st_mode) & 0o077):
            raise IntegrityError("launcher lock is not a private owner-only regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise AdmissionDeferred("another launcher deployment holds the transaction lock") from error
        yield
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _lock_is_held(config: Config) -> bool:
    lock_path = config.state_root / "launcher.lock"
    try:
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise IntegrityError(f"cannot inspect launcher lock: {type(error).__name__}") from error
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


def _selected_reference(config: Config) -> dict[str, str]:
    # If no transaction owns the lock, read active while briefly owning it so a
    # deploy cannot stage a candidate between the lock check and selector read.
    lock_path = config.state_root / "launcher.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            selector = _read_selector(config)
            candidate = selector["candidate"]
            active = selector["active"]
            if candidate is not None:
                return candidate
            if active is not None:
                return active
            raise IntegrityError("deployment transaction has no selected Brain release")
        selector = _read_selector(config)
        active = selector["active"]
        if active is None:
            raise IntegrityError("no active Brain release is selected")
        return active
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


class _GuardedPath(list[str]):
    def __init__(self, values: list[str], source: Path):
        self._source = source
        super().__init__(value for value in values if self._allowed(value))

    def _allowed(self, value: object) -> bool:
        if not isinstance(value, str):
            return False
        try:
            candidate = Path(value or os.getcwd()).resolve()
        except OSError:
            return False
        return not _is_within(candidate, self._source)

    def append(self, value: str) -> None:
        if self._allowed(value):
            super().append(value)

    def insert(self, index: int, value: str) -> None:
        if self._allowed(value):
            super().insert(index, value)

    def extend(self, values) -> None:
        super().extend(value for value in values if self._allowed(value))

    def __iadd__(self, values):
        self.extend(values)
        return self


class _SnapshotLoader(importlib.abc.Loader):
    def __init__(self, fullname: str, raw: bytes, virtual_file: str, is_package: bool):
        self.fullname = fullname
        self.raw = raw
        self.virtual_file = virtual_file
        self.is_package = is_package

    def create_module(self, spec):
        return None

    def exec_module(self, module) -> None:
        module.__file__ = self.virtual_file
        module.__loader__ = self
        if self.is_package:
            module.__path__ = [str(Path(self.virtual_file).parent)]
            module.__package__ = self.fullname
        code = compile(self.raw, self.virtual_file, "exec", dont_inherit=True)
        exec(code, module.__dict__)


class _SnapshotFinder(importlib.abc.MetaPathFinder):
    def __init__(self, source: Path, sources: dict[str, bytes]):
        self.source = source
        self.modules: dict[str, tuple[bytes, str, bool]] = {}
        for relative, raw in sources.items():
            pure = PurePosixPath(relative)
            if pure.parts[0] != "scripts" or pure.suffix != ".py":
                continue
            module_parts = list(pure.parts[1:])
            is_package = module_parts[-1] == "__init__.py"
            if is_package:
                module_parts = module_parts[:-1]
            else:
                module_parts[-1] = pure.stem
            if not module_parts:
                continue
            fullname = ".".join(module_parts)
            if fullname in self.modules:
                raise IntegrityError(f"snapshot has duplicate module identity: {fullname}")
            self.modules[fullname] = (raw, str(source / relative), is_package)

    def find_spec(self, fullname: str, path=None, target=None):
        value = self.modules.get(fullname)
        if value is None:
            search = path if path is not None else sys.path
            try:
                fallback = importlib.machinery.PathFinder.find_spec(fullname, search)
            except (ImportError, AttributeError, TypeError, ValueError):
                fallback = None
            origin = getattr(fallback, "origin", None)
            if isinstance(origin, str) and origin not in ("built-in", "frozen"):
                try:
                    if _is_within(Path(origin).resolve(), self.source):
                        raise ImportError(f"mutable checkout import blocked: {fullname}")
                except OSError:
                    raise ImportError(f"unresolvable checkout import blocked: {fullname}")
            return None
        raw, virtual_file, is_package = value
        loader = _SnapshotLoader(fullname, raw, virtual_file, is_package)
        return importlib.util.spec_from_loader(
            fullname, loader, origin=virtual_file, is_package=is_package,
        )


@contextlib.contextmanager
def _snapshot_runtime(config: Config, release: Release) -> Iterator[None]:
    finder = _SnapshotFinder(config.source_root, release.sources)
    saved_path = sys.path
    saved_meta = list(sys.meta_path)
    saved_executable = sys.executable
    saved_argv = list(sys.argv)
    saved_modules = {name: sys.modules.get(name) for name in finder.modules}
    saved_importer_cache = dict(sys.path_importer_cache)
    environment_updates = {
        ENV_MANIFEST: str(release.manifest_path),
        ENV_MANIFEST_SHA: release.manifest_sha256,
        ENV_SOURCE: str(config.source_root),
        ENV_BRANCH: config.branch,
        ENV_STATE: str(config.state_root),
        ENV_SELECTION: str(config.selection),
        ENV_HELPER_STATE: str(config.helper_state),
        ENV_SERVICE: config.service,
        ENV_HOST: config.host,
        ENV_PORT: str(config.port),
    }
    saved_environment = {key: os.environ.get(key) for key in environment_updates}
    try:
        for name in finder.modules:
            sys.modules.pop(name, None)
        sys.path = _GuardedPath(list(saved_path), config.source_root)
        sys.meta_path.insert(0, finder)
        sys.executable = str(config.launcher_path)
        os.environ.update(environment_updates)
        for cached in list(sys.path_importer_cache):
            try:
                if _is_within(Path(cached or os.getcwd()).resolve(), config.source_root):
                    del sys.path_importer_cache[cached]
            except OSError:
                del sys.path_importer_cache[cached]
        yield
    finally:
        for name in finder.modules:
            sys.modules.pop(name, None)
        for name, module in saved_modules.items():
            if module is not None:
                sys.modules[name] = module
        sys.path = saved_path
        sys.meta_path[:] = saved_meta
        sys.executable = saved_executable
        sys.argv[:] = saved_argv
        sys.path_importer_cache.clear()
        sys.path_importer_cache.update(saved_importer_cache)
        for key, value in saved_environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _system_exit_code(error: SystemExit) -> int:
    if error.code is None:
        return 0
    if isinstance(error.code, int):
        return error.code
    print(error.code, file=sys.stderr)
    return 1


def _execute_entry(config: Config, release: Release, relative: str,
                   arguments: list[str]) -> int:
    raw = release.sources.get(relative)
    if raw is None:
        raise IntegrityError(f"requested Python entrypoint is absent from release: {relative}")
    virtual_file = str(config.source_root / relative)
    module = types.ModuleType("__main__")
    module.__file__ = virtual_file
    module.__package__ = None
    module.__cached__ = None
    saved_main = sys.modules.get("__main__")
    with _snapshot_runtime(config, release):
        sys.argv = [virtual_file, *arguments]
        sys.modules["__main__"] = module
        try:
            exec(compile(raw, virtual_file, "exec", dont_inherit=True), module.__dict__)
        except SystemExit as error:
            return _system_exit_code(error)
        finally:
            if saved_main is None:
                sys.modules.pop("__main__", None)
            else:
                sys.modules["__main__"] = saved_main
    return 0


def _read_applied_state(config: Config) -> dict[str, object] | None:
    if not config.helper_state.exists():
        return None
    raw = _regular_bytes(config.helper_state, limit=65_536)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntegrityError("helper applied state is not valid JSON") from error
    if not isinstance(value, dict):
        raise IntegrityError("helper applied state is not an object")
    return value


def _prepare_command(config: Config) -> int:
    with _deploy_lock(config):
        selector = _read_selector(config)
        if selector["candidate"] is not None:
            _atomic_json(config.selection, {
                "schema_version": SCHEMA_VERSION,
                "active": selector["active"],
                "candidate": None,
            })
        release = _prepare_release(config)
    print(_canonical_json(_descriptor(release)).decode("utf-8"))
    return 0


def _deploy_command(config: Config) -> int:
    with _deploy_lock(config):
        before = _read_selector(config)
        previous = before["active"]
        if before["candidate"] is not None:
            _atomic_json(config.selection, {
                "schema_version": SCHEMA_VERSION, "active": previous, "candidate": None,
            })
        release = _prepare_release(config)
        candidate = release.reference
        staged = {"schema_version": SCHEMA_VERSION, "active": previous, "candidate": candidate}
        _atomic_json(config.selection, staged)
        helper_arguments = [
            "--source", str(config.source_root),
            "--state", str(config.helper_state),
            "--branch", config.branch,
            "--service", config.service,
            "--release-manifest", str(release.manifest_path),
            "--release-manifest-sha256", release.manifest_sha256,
            "--selection", str(config.selection),
        ]
        try:
            release = _verify_release(config, release.manifest_path, release.manifest_sha256)
            code = _execute_entry(config, release, ENTRYPOINT_DEPLOY, helper_arguments)
        except Exception:
            _atomic_json(config.selection, {
                "schema_version": SCHEMA_VERSION, "active": previous, "candidate": None,
            })
            raise
        if code != 0:
            _atomic_json(config.selection, {
                "schema_version": SCHEMA_VERSION, "active": previous, "candidate": None,
            })
            return code

        applied = _read_applied_state(config)
        applied_sha = applied.get("manifest_sha256") if applied else None
        if applied_sha == release.manifest_sha256:
            _atomic_json(config.selection, {
                "schema_version": SCHEMA_VERSION, "active": candidate, "candidate": None,
            })
            status = "applied"
        elif previous is not None:
            old_release = _verify_release(
                config, Path(previous["manifest_path"]), previous["manifest_sha256"],
            )
            if old_release.manifest["runtime_fingerprint"] != release.manifest["runtime_fingerprint"]:
                _atomic_json(config.selection, {
                    "schema_version": SCHEMA_VERSION, "active": previous, "candidate": None,
                })
                raise IntegrityError("helper returned success without a matching applied manifest receipt")
            _atomic_json(config.selection, {
                "schema_version": SCHEMA_VERSION, "active": previous, "candidate": None,
            })
            status = "qualified_noop"
        else:
            _atomic_json(config.selection, {
                "schema_version": SCHEMA_VERSION, "active": None, "candidate": None,
            })
            raise IntegrityError("first deployment returned success without an applied manifest receipt")
    print(_canonical_json({"status": status, **_descriptor(release)}).decode("utf-8"))
    return 0


def _serve_command(config: Config) -> int:
    reference = _selected_reference(config)
    release = _verify_release(
        config, Path(reference["manifest_path"]), reference["manifest_sha256"],
    )
    return _execute_entry(
        config, release, ENTRYPOINT_SERVE,
        ["--host", config.host, "--port", str(config.port)],
    )


def _shim_arguments() -> tuple[Config, Path, str, str, list[str]]:
    required = (
        ENV_MANIFEST, ENV_MANIFEST_SHA, ENV_SOURCE, ENV_BRANCH, ENV_STATE,
        ENV_SELECTION, ENV_HELPER_STATE, ENV_SERVICE, ENV_HOST, ENV_PORT,
    )
    if any(not os.environ.get(key) for key in required):
        raise InterfaceError("Python-script shim requires a verified release environment")
    if len(sys.argv) < 2:
        raise InterfaceError("Python-script shim requires a canonical script path")
    parser_value = argparse.Namespace(
        source=Path(os.environ[ENV_SOURCE]),
        branch=os.environ[ENV_BRANCH],
        state_root=Path(os.environ[ENV_STATE]),
        selection=Path(os.environ[ENV_SELECTION]),
        helper_state=Path(os.environ[ENV_HELPER_STATE]),
        service=os.environ[ENV_SERVICE],
        host=os.environ[ENV_HOST],
        port=int(os.environ[ENV_PORT]),
    )
    config = _config(parser_value)
    requested = Path(sys.argv[1])
    if not requested.is_absolute():
        raise InterfaceError("Python-script shim path must be absolute")
    try:
        relative = requested.relative_to(config.source_root).as_posix()
    except ValueError as error:
        raise InterfaceError("Python-script shim path is outside the canonical source") from error
    if not relative.startswith("scripts/") or not relative.endswith(".py"):
        raise InterfaceError("Python-script shim accepts only canonical scripts/*.py paths")
    return config, Path(os.environ[ENV_MANIFEST]), os.environ[ENV_MANIFEST_SHA], relative, sys.argv[2:]


def _looks_like_shim() -> bool:
    return len(sys.argv) > 1 and sys.argv[1].startswith("/") and sys.argv[1].endswith(".py")


def _parser() -> Parser:
    parser = Parser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True, parser_class=Parser)
    for mode in ("prepare", "deploy", "serve"):
        subparser = subparsers.add_parser(mode)
        subparser.add_argument("--source", type=Path, required=True)
        subparser.add_argument("--branch", default="main")
        subparser.add_argument("--state-root", type=Path, required=True)
        subparser.add_argument("--selection", type=Path)
        subparser.add_argument("--helper-state", type=Path)
        subparser.add_argument("--service", default="brain.service")
        subparser.add_argument("--host", default="0.0.0.0")
        subparser.add_argument("--port", type=int, default=5180)
    return parser


def main() -> int:
    try:
        if sys.flags.isolated != 1:
            raise InterfaceError("launcher requires an isolated Python interpreter (-I)")
        if _looks_like_shim():
            config, manifest_path, manifest_sha, relative, arguments = _shim_arguments()
            release = _verify_release(config, manifest_path, manifest_sha)
            return _execute_entry(config, release, relative, arguments)
        arguments = _parser().parse_args()
        config = _config(arguments)
        if arguments.mode == "prepare":
            return _prepare_command(config)
        if arguments.mode == "deploy":
            return _deploy_command(config)
        if arguments.mode == "serve":
            return _serve_command(config)
        raise InterfaceError("unsupported launcher mode")
    except LaunchError as error:
        print(f"brain-launch: {error}", file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
