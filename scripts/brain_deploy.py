#!/usr/bin/env python3
"""Restart the Brain service once for each clean deployment to a Git branch."""
import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


Runner = Callable[..., subprocess.CompletedProcess[str]]
STATE_SCHEMA_VERSION = 1
SOURCE_PATHS = ("scripts", "memory/brain/view", "systemd/user")


class DeploymentError(RuntimeError):
    """Raised when deployment state cannot be trusted or a service action fails."""


@dataclass(frozen=True)
class DeploymentResult:
    status: str
    detail: str
    fingerprint: str | None = None


def command_result(command: list[str], *, source: Path, runner: Runner) -> subprocess.CompletedProcess[str]:
    try:
        return runner(command, cwd=source, text=True, capture_output=True, check=False,
                      timeout=20, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except subprocess.TimeoutExpired as error:
        raise DeploymentError(f"command timed out: {command[0]}") from error


def command_output(command: list[str], *, source: Path, runner: Runner) -> str:
    result = command_result(command, source=source, runner=runner)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise DeploymentError(f"{' '.join(command)}: {detail}")
    return result.stdout.strip()


def git_output(source: Path, *arguments: str, runner: Runner) -> str:
    return command_output(["git", "-C", str(source), *arguments], source=source, runner=runner)


def source_fingerprint(source: Path, branch: str, runner: Runner) -> DeploymentResult:
    source = source.resolve()
    top_level = Path(git_output(source, "rev-parse", "--show-toplevel", runner=runner)).resolve()
    if top_level != source:
        return DeploymentResult("deferred", f"source is not its Git top level: {top_level}")

    index_lock = Path(git_output(source, "rev-parse", "--git-path", "index.lock", runner=runner))
    if not index_lock.is_absolute():
        index_lock = source / index_lock
    if index_lock.exists():
        return DeploymentResult("deferred", f"Git index is busy: {index_lock}")

    checked_out = command_result(["git", "-C", str(source), "symbolic-ref", "--quiet", "--short", "HEAD"], source=source, runner=runner)
    if checked_out.returncode != 0 or checked_out.stdout.strip() != branch:
        return DeploymentResult("deferred", f"checked-out branch is not {branch}")

    branch_ref = f"refs/heads/{branch}^{{commit}}"
    branch_commit = git_output(source, "rev-parse", "--verify", branch_ref, runner=runner)
    head_commit = git_output(source, "rev-parse", "HEAD^{commit}", runner=runner)
    if head_commit != branch_commit:
        return DeploymentResult("deferred", f"HEAD {head_commit} does not match {branch} {branch_commit}")

    staged = git_output(source, "diff", "--cached", "--name-only", runner=runner)
    if staged:
        return DeploymentResult("deferred", "Git index has staged changes")
    changes = git_output(source, "status", "--porcelain", "--untracked-files=all", "--", *SOURCE_PATHS, runner=runner)
    if changes:
        return DeploymentResult("deferred", "runtime source has uncommitted or untracked changes")
    tree = git_output(source, "ls-tree", "-r", "--full-tree", head_commit, "--", *SOURCE_PATHS, runner=runner)
    if not tree:
        return DeploymentResult("deferred", "no committed runtime source files")
    fingerprint = hashlib.sha256(tree.encode()).hexdigest()
    return DeploymentResult("ready", "clean committed runtime source; unrelated operator/data files preserved", fingerprint)


def read_state(state: Path) -> str | None:
    if not state.exists():
        return None
    try:
        payload = json.loads(state.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise DeploymentError(f"cannot read deployment state {state}: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != STATE_SCHEMA_VERSION:
        raise DeploymentError(f"deployment state {state} has an unknown schema")
    fingerprint = payload.get("fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise DeploymentError(f"deployment state {state} has no fingerprint")
    return fingerprint


def write_state(state: Path, fingerprint: str) -> None:
    state.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": STATE_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=state.parent, delete=False) as temporary_file:
            temporary_path = temporary_file.name
            json.dump(payload, temporary_file, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, state)
    except OSError as error:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)
        raise DeploymentError(f"cannot write deployment state {state}: {error}") from error


@contextmanager
def deployment_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def service_active(service: str, source: Path, runner: Runner) -> bool:
    result = command_result(["systemctl", "--user", "is-active", "--quiet", service], source=source, runner=runner)
    return result.returncode == 0


def restart_service(service: str, source: Path, runner: Runner) -> None:
    result = command_result(["systemctl", "--user", "restart", service], source=source, runner=runner)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "restart failed"
        raise DeploymentError(f"cannot restart {service}: {detail}")
    if not service_active(service, source, runner):
        raise DeploymentError(f"{service} is not active after restart")


def service_ready() -> bool:
    """Bounded read-only API readiness; never draft a card or invoke a model."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(3):
        try:
            for route in ("summary", "operations"):
                with opener.open(f"http://127.0.0.1:5180/api/{route}", timeout=3) as response:
                    data = json.load(response)
                if not isinstance(data, dict):
                    raise ValueError("not an object")
                if route == "summary" and not isinstance(data.get("status_strip"), dict):
                    raise ValueError("unsupported summary")
                if route == "operations" and not (data.get("read_only") is True and
                        isinstance(data.get("server"), dict) and
                        data["server"].get("alive", {}).get("value") is True):
                    raise ValueError("unsupported operations")
            return True
        except (OSError, ValueError, AttributeError, urllib.error.URLError):
            if attempt < 2:
                time.sleep(0.25)
    return False


def deploy(source: Path, state: Path, branch: str, service: str, runner: Runner = subprocess.run) -> DeploymentResult:
    source = source.resolve()
    state = state.resolve()
    with deployment_lock(state.with_suffix(state.suffix + ".lock")) as lock_acquired:
        if not lock_acquired:
            return DeploymentResult("deferred", "another deployment check holds the lock")
        current = source_fingerprint(source, branch, runner)
        if current.status != "ready":
            return current
        assert current.fingerprint is not None
        recorded = read_state(state)
        if recorded == current.fingerprint:
            return DeploymentResult("unchanged", "fingerprint already deployed", current.fingerprint)
        before_restart = source_fingerprint(source, branch, runner)
        if before_restart.status != "ready" or before_restart.fingerprint != current.fingerprint:
            return DeploymentResult("deferred", "source changed before restart")
        restart_service(service, source, runner)
        if not service_ready():
            raise DeploymentError("Brain API readiness failed; previous fingerprint retained")
        after_restart = source_fingerprint(source, branch, runner)
        if after_restart.status != "ready" or after_restart.fingerprint != current.fingerprint:
            return DeploymentResult("deferred", "source changed during restart")
        write_state(state, current.fingerprint)
        return DeploymentResult("restarted", "service restarted for new fingerprint", current.fingerprint)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--service", default="brain.service")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    try:
        result = deploy(
            arguments.source,
            arguments.state,
            arguments.branch,
            arguments.service,
        )
    except DeploymentError as error:
        print(f"brain-deploy: error: {error}", file=sys.stderr)
        return 1
    fingerprint = f" {result.fingerprint}" if result.fingerprint else ""
    print(f"brain-deploy: {result.status}: {result.detail}{fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
