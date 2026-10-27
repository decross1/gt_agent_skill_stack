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

PACKS = ("core", "meta", "research", "brain", "design")
RUNTIME_CORE = frozenset({"resume-state", "gate-check", "validate", "fallback",
                          "run-log", "spawn-contract"})
MAX_FILE_BYTES = 64 * 1024
MAX_ENTRIES = 256
NAME = re.compile(r"[a-z][a-z0-9-]{0,63}")


class BoundaryError(ValueError):
    pass


def _identity(info: os.stat_result) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _scan(fd: int) -> list[str]:
    with os.scandir(fd) as entries:
        names = []
        for entry in entries:
            if len(names) >= MAX_ENTRIES:
                raise BoundaryError("directory entry limit exceeded")
            names.append(entry.name)
    return sorted(names)


class _Snapshot:
    def __init__(self, root: str | Path):
        self.root = root
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.directories = {(): (fd, _identity(os.fstat(fd)))}
        self.files = {}
        self.listings = {}
        self.receipts = {}

    def directory(self, parts: tuple[str, ...]) -> int:
        if parts not in self.directories:
            parent = self.directory(parts[:-1])
            fd = os.open(parts[-1], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=parent)
            self.directories[parts] = (fd, _identity(os.fstat(fd)))
        return self.directories[parts][0]

    def entries(self, parts: tuple[str, ...]) -> list[str]:
        fd = self.directory(parts)
        names = _scan(fd)
        if _identity(os.fstat(fd)) != self.directories[parts][1]:
            raise BoundaryError("directory changed during capture")
        self.listings[parts] = names
        return names

    def read(self, parts: tuple[str, ...]) -> str:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                     dir_fd=self.directory(parts[:-1]))
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
                raise BoundaryError("input is not a bounded regular file")
            raw = stream.read(MAX_FILE_BYTES + 1)
            after = os.fstat(stream.fileno())
            if len(raw) > MAX_FILE_BYTES or len(raw) != before.st_size or _identity(before) != _identity(after):
                raise BoundaryError("input exceeded its bound or changed during capture")
        self.files[parts] = _identity(before)
        self.receipts["/".join(parts)] = hashlib.sha256(raw).hexdigest()
        return raw.decode("utf-8")

    def check(self) -> None:
        for parts, identity in self.files.items():
            info = os.stat(parts[-1], dir_fd=self.directory(parts[:-1]), follow_symlinks=False)
            if _identity(info) != identity:
                raise BoundaryError("input pathname changed during capture")
        for parts, (fd, identity) in self.directories.items():
            info = (os.stat(parts[-1], dir_fd=self.directory(parts[:-1]), follow_symlinks=False)
                    if parts else os.stat(self.root, follow_symlinks=False))
            if _identity(info) != identity or _identity(os.fstat(fd)) != identity:
                raise BoundaryError("directory pathname changed during capture")
            if parts in self.listings and _scan(fd) != self.listings[parts]:
                raise BoundaryError("directory inventory changed during capture")

    def close(self) -> None:
        for fd, _ in self.directories.values():
            os.close(fd)


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


def _documented_packs(text: str) -> dict[str, set[str]]:
    """Require agreement with the documented inventory, including dev core."""
    declared = {}
    counts = {}
    section = None
    tick = chr(96)
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            if cells and cells[0] in {tick + pack + tick for pack in PACKS}:
                pack = cells[0][1:-1]
                if len(cells) != 5 or pack in counts or not cells[3].isdigit():
                    raise BoundaryError("malformed or duplicate documented pack count")
                counts[pack] = int(cells[3])
        if line.startswith("## "):
            section = None
        elif line.startswith("### "):
            match = re.fullmatch("### " + tick + r"([a-z]+)" + tick + r" \([^)]+\)", line)
            section = match[1] if match and match[1] in PACKS else None
            if section:
                if section in declared:
                    raise BoundaryError("duplicate documented pack section")
                declared[section] = set()
        elif section and line.startswith("- "):
            match = re.fullmatch("- " + tick + r"([a-z][a-z0-9-]{0,63})" + tick
                                 + r"(?: \([ABC]\))? — .+", line)
            if not match or match[1] in set().union(*declared.values()):
                raise BoundaryError("malformed or duplicate documented skill")
            declared[section].add(match[1])
    if set(declared) != set(PACKS) or set(counts) != set(PACKS):
        raise BoundaryError("five documented pack sections and counts are required")
    if any(not names or len(names) != counts[pack] for pack, names in declared.items()):
        raise BoundaryError("documented pack count differs from its membership")
    totals = re.findall(r"^Total: ([0-9]+) skills today\.$", text, re.MULTILINE)
    if len(totals) != 1 or int(totals[0]) != sum(counts.values()):
        raise BoundaryError("documented total differs from pack counts")
    return declared


def verify_pack_boundary(repo_root: str | Path) -> dict:
    """Read only regular, nonsymlink inputs beneath one opened repository root."""
    try:
        snapshot = _Snapshot(repo_root)
    except OSError as exc:
        raise BoundaryError("repository root unavailable or symlinked") from exc
    try:
        expected_core = _boundary_core(snapshot.read(("BOUNDARY.md",)))
        declared = _documented_packs(snapshot.read((".agents", "PACKS.md")))
        if not expected_core <= declared["core"]:
            raise BoundaryError("documented core omits required runtime skills")
        if set(snapshot.entries(("packs",))) != {pack + ".txt" for pack in PACKS}:
            raise BoundaryError("exactly five pack manifests are required")
        expected = {pack: set() for pack in PACKS}
        excluded = []
        skill_names = snapshot.entries((".agents", "skills"))
        if set(skill_names) != set().union(*declared.values()):
            raise BoundaryError("skill inventory differs from documented pack membership")
        for skill in skill_names:
            if NAME.fullmatch(skill) is None:
                raise BoundaryError("invalid skill directory name")
            fields = _frontmatter(snapshot.read((".agents", "skills", skill, "SKILL.md")), skill)
            layer, safe, pack = (fields[key] for key in ("layer", "runtime-safe", "pack"))
            if pack not in PACKS or layer not in ("A", "B", "C") or safe not in ("true", "false"):
                raise BoundaryError(f"{skill}: invalid classification")
            if skill not in declared[pack]:
                raise BoundaryError(f"{skill}: frontmatter disagrees with documented pack")
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
            names = _manifest(snapshot.read(("packs", pack + ".txt")))
            if seen & names:
                raise BoundaryError("skill occurs in multiple manifests")
            seen.update(names)
            if names != expected[pack]:
                raise BoundaryError(f"{pack}: manifest differs from its required skill projection")
            manifests[pack] = sorted(names)
        snapshot.check()
        return {"ok": True, "packs": manifests, "total_skills": len(skill_names),
                "manifested_skills": len(seen), "excluded_dev_core": sorted(excluded),
                "scope": "manifest composition only; core is the runtime-safe projection",
                "runtime_conformance_verified": False, "input_sha256": snapshot.receipts}
    except (OSError, UnicodeError) as exc:
        raise BoundaryError("unreadable or unsafe repository input") from exc
    finally:
        snapshot.close()


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
