#!/usr/bin/env python3
"""Verify manifest composition, not runtime conformance or installation.

Core projects the runtime-safe frontmatter core pack; dev-only core extensions
remain outside these manifests and are reported explicitly.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat

PACKS = ("core", "meta", "research", "brain")
RUNTIME_CORE = frozenset({"resume-state", "gate-check", "validate", "fallback",
                          "run-log", "spawn-contract"})
MAX_FILE_BYTES = 64 * 1024
MAX_ENTRIES = 256
NAME = re.compile(r"[a-z][a-z0-9-]{0,63}")


class BoundaryError(ValueError):
    pass


def _open_at(root_fd: int, parts: tuple[str, ...], *, directory=False) -> int:
    parent = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=parent)
            os.close(parent)
            parent = child
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        flags |= os.O_DIRECTORY if directory else os.O_NONBLOCK
        return os.open(parts[-1], flags, dir_fd=parent)
    finally:
        os.close(parent)


def _entries(root_fd: int, parts: tuple[str, ...]) -> list[str]:
    fd = _open_at(root_fd, parts, directory=True)
    try:
        with os.scandir(fd) as entries:
            names = []
            for entry in entries:
                if len(names) >= MAX_ENTRIES:
                    raise BoundaryError("directory entry limit exceeded")
                names.append(entry.name)
        return sorted(names)
    finally:
        os.close(fd)


def _read(root_fd: int, parts: tuple[str, ...], receipts: dict) -> str:
    fd = _open_at(root_fd, parts)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
            raise BoundaryError("input is not a bounded regular file")
        raw = stream.read(MAX_FILE_BYTES + 1)
        after = os.fstat(stream.fileno())
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(raw) > MAX_FILE_BYTES or len(raw) != before.st_size or identity(before) != identity(after):
            raise BoundaryError("input exceeded its bound or changed during capture")
    receipts["/".join(parts)] = hashlib.sha256(raw).hexdigest()
    return raw.decode("utf-8")


def _frontmatter(text: str, skill: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise BoundaryError(f"{skill}: missing frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise BoundaryError(f"{skill}: unterminated frontmatter") from exc
    fields = {}
    for line in lines[1:end]:
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-z][a-z0-9_-]*):[ \t]+(\S.*)", line)
        if match is None:
            raise BoundaryError(f"{skill}: expected canonical one-line frontmatter scalars")
        key, value = match.groups()
        value = value.strip()
        if key in fields or not value or value[0] in "[{!&*|>\"'":
            raise BoundaryError(f"{skill}: duplicate or noncanonical frontmatter")
        fields[key] = value
    if not {"name", "layer", "runtime-safe", "pack", "description"}.issubset(fields):
        raise BoundaryError(f"{skill}: incomplete frontmatter")
    if fields["name"] != skill or not "\n".join(lines[end + 1:]).strip():
        raise BoundaryError(f"{skill}: mismatched name or empty skill body")
    return fields


def _boundary_core(text: str) -> set[str]:
    lines = text.splitlines()
    tick = chr(96)
    heading = f"**Runtime-safe core — Layer A** ({tick}runtime-safe: true{tick}). The six"
    starts = [i for i, line in enumerate(lines) if line == heading]
    if len(starts) != 1:
        raise BoundaryError("BOUNDARY.md lacks one canonical runtime-core declaration")
    paragraph = []
    for line in lines[starts[0]:]:
        if not line.strip():
            break
        paragraph.append(line)
    names = re.findall(tick + r"([a-z][a-z0-9-]*)" + tick, "\n".join(paragraph))
    if len(names) != len(RUNTIME_CORE) or set(names) != RUNTIME_CORE:
        raise BoundaryError("BOUNDARY.md runtime core differs from the six-skill contract")
    return set(names)


def _manifest(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if NAME.fullmatch(value) is None or value in names:
            raise BoundaryError("invalid or duplicate manifest entry")
        names.add(value)
    if not names:
        raise BoundaryError("empty manifest")
    return names


def verify_pack_boundary(repo_root: str | Path) -> dict:
    """Read only regular, nonsymlink inputs beneath one opened repository root."""
    try:
        root_fd = os.open(repo_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    except OSError as exc:
        raise BoundaryError("repository root unavailable or symlinked") from exc
    try:
        receipts = {}
        expected_core = _boundary_core(_read(root_fd, ("BOUNDARY.md",), receipts))
        if set(_entries(root_fd, ("packs",))) != {pack + ".txt" for pack in PACKS}:
            raise BoundaryError("exactly four pack manifests are required")
        expected = {pack: set() for pack in PACKS}
        excluded = []
        skill_names = _entries(root_fd, (".agents", "skills"))
        for skill in skill_names:
            if NAME.fullmatch(skill) is None:
                raise BoundaryError("invalid skill directory name")
            fields = _frontmatter(_read(root_fd, (".agents", "skills", skill, "SKILL.md"), receipts), skill)
            layer, safe, pack = (fields[key] for key in ("layer", "runtime-safe", "pack"))
            if pack not in PACKS or layer not in ("A", "B", "C") or safe not in ("true", "false"):
                raise BoundaryError(f"{skill}: invalid classification")
            if layer == "A":
                if safe != "true" or pack != "core" or skill not in expected_core:
                    raise BoundaryError(f"{skill}: invalid runtime-core classification")
                expected["core"].add(skill)
            else:
                if safe != "false" or layer != ("C" if pack == "meta" else "B"):
                    raise BoundaryError(f"{skill}: dev-only classification leaks runtime safety")
                if pack == "core":
                    excluded.append(skill)
                else:
                    expected[pack].add(skill)
        if expected["core"] != expected_core:
            raise BoundaryError("runtime-safe skill inventory differs from BOUNDARY.md")
        seen = set()
        manifests = {}
        for pack in PACKS:
            names = _manifest(_read(root_fd, ("packs", pack + ".txt"), receipts))
            if seen & names:
                raise BoundaryError("skill occurs in multiple manifests")
            seen.update(names)
            if names != expected[pack]:
                raise BoundaryError(f"{pack}: manifest differs from its required skill projection")
            manifests[pack] = sorted(names)
        return {"ok": True, "packs": manifests, "total_skills": len(skill_names),
                "manifested_skills": len(seen), "excluded_dev_core": sorted(excluded),
                "scope": "manifest composition only; core is the runtime-safe projection",
                "runtime_conformance_verified": False, "input_sha256": receipts}
    except (OSError, UnicodeError) as exc:
        raise BoundaryError("unreadable or unsafe repository input") from exc
    finally:
        os.close(root_fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        report = verify_pack_boundary(args.repo_root)
    except BoundaryError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
