#!/usr/bin/env python3
"""pi_discovery_check.py — mock what a Pi runtime would do at init.

Walk ~/.pi/agent/skills/ (or a path given via --skills-dir), dereference each
symlink, parse SKILL.md frontmatter, and report per-skill loadable/error
status. Intended as a pre-flight check before a real Pi deployment.

Exit 0 iff every skill in the directory is loadable AND has runtime-safe: true
in its frontmatter (the firewall invariant).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_DIR = Path.home() / ".pi" / "agent" / "skills"
REQUIRED_FIELDS = {"name", "layer", "runtime-safe", "description"}
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    m = FM_RE.match(text)
    if not m:
        return None
    fm: dict[str, str] = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def check_skill(link: Path) -> tuple[str, str, dict[str, str] | None]:
    if not link.is_symlink() and not link.is_dir():
        return ("error", "not a symlink or directory", None)
    target = link.resolve()
    if not target.exists():
        return ("error", f"broken symlink → {target}", None)
    skill_md = target / "SKILL.md"
    if not skill_md.exists():
        return ("error", "no SKILL.md in target", None)
    fm = parse_frontmatter(skill_md.read_text())
    if fm is None:
        return ("error", "frontmatter missing or malformed", None)
    missing = REQUIRED_FIELDS - set(fm.keys())
    if missing:
        return ("error", f"missing fields: {sorted(missing)}", fm)
    if fm.get("runtime-safe") != "true":
        return ("violation", f"runtime-safe={fm.get('runtime-safe')!r} (must be 'true' in Pi)", fm)
    if fm.get("layer") not in ("A", "B", "C"):
        return ("error", f"invalid layer={fm.get('layer')!r}", fm)
    return ("ok", "loadable", fm)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock Pi runtime skill discovery.")
    parser.add_argument("--skills-dir", default=str(DEFAULT_DIR))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir)
    print(f"Discovering skills in {skills_dir}")
    if not skills_dir.exists():
        print(f"  (directory does not exist — Pi has nothing to load)")
        return 0

    entries = sorted(p for p in skills_dir.iterdir() if not p.name.startswith("."))
    if not entries:
        print(f"  (directory empty)")
        return 0

    results = [(p.name, *check_skill(p)) for p in entries]
    ok = sum(1 for _, st, *_ in results if st == "ok")
    errs = sum(1 for _, st, *_ in results if st == "error")
    viols = sum(1 for _, st, *_ in results if st == "violation")

    if not args.quiet:
        for name, status, msg, fm in results:
            mark = {"ok": "✓", "error": "✗", "violation": "⚠"}[status]
            extra = f" [layer={fm.get('layer','?')}]" if fm else ""
            print(f"  {mark} {name:<20} {status:<10}{extra}  {msg}")

    print(f"\n  total: {len(results)}  ok: {ok}  errors: {errs}  violations: {viols}")
    return 0 if (errs == 0 and viols == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
