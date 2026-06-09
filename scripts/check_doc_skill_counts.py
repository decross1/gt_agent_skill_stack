#!/usr/bin/env python3
"""check_doc_skill_counts.py - assert docs match the skills on disk.

Doc-drift guard. The framework's prose names a count of runtime-safe skills and
AGENTS.md carries per-layer tables that must list every skill of that layer.
Both drift when a skill is added (spawn-contract took the core 5 -> 6 but the
docs still said "five" and omitted the row). This is the falsifiable check.

  1. SKILL.md frontmatter -> per-layer sets + runtime-safe:true set (truth).
  2. AGENTS.md per-layer tables must equal the on-disk per-layer sets.
  3. Stale runtime-safe count words ("five"/"5 Layer-A") in any of the 4 docs.
  4. Inline core enumerations must name every runtime-safe skill.

Exit 0 + "OK" iff all match; else "FAIL" with each discrepancy and exit 1.
plan.md's append-only ## Sessions journal is not asserted (never rewritten).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / ".agents" / "skills"

NUMWORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
            7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
            12: "twelve"}

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
LAYER_HEADING_RE = re.compile(r"^###\s+Layer\s+([ABC])\b")
OTHER_HEADING_RE = re.compile(r"^#{1,3}\s+")
TABLE_SKILL_RE = re.compile(r"^\|\s*`([a-z][a-z0-9-]+)`\s*\|")


def parse_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def disk_truth():
    """Return ({layer: {skills}}, {runtime_safe}) from SKILL.md files."""
    by_layer = {"A": set(), "B": set(), "C": set()}
    runtime_safe = set()
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        name = skill_md.parent.name
        fm = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        layer = fm.get("layer", "").strip()
        if layer not in by_layer:
            print("FAIL: %s: bad/absent layer frontmatter: %r" % (name, layer))
            sys.exit(1)
        by_layer[layer].add(name)
        if fm.get("runtime-safe", "").strip().lower() == "true":
            runtime_safe.add(name)
    return by_layer, runtime_safe


def agents_md_tables():
    """AGENTS.md per-layer tables -> {layer: {skills}}.

    Rows attribute to the most recent '### Layer X'; any other heading closes
    that scope so the '## Agents' profile table is not read as Layer-C skills.
    """
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    tables = {"A": set(), "B": set(), "C": set()}
    current = None
    for line in text.splitlines():
        h = LAYER_HEADING_RE.match(line)
        if h:
            current = h.group(1)
            continue
        if current is not None and OTHER_HEADING_RE.match(line):
            current = None
            continue
        if current is None:
            continue
        m = TABLE_SKILL_RE.match(line)
        if m:
            tables[current].add(m.group(1))
    return tables


def word_to_n(w):
    w = w.lower()
    for k, v in NUMWORDS.items():
        if v == w:
            return k
    return int(w) if w.isdigit() else None


def main():
    by_layer, runtime_safe = disk_truth()
    n_rs = len(runtime_safe)
    correct = NUMWORDS.get(n_rs, str(n_rs))
    problems = []

    if runtime_safe != by_layer["A"]:
        problems.append(
            "runtime-safe:true set != Layer-A set on disk "
            "(runtime-safe=%s, A=%s)" % (sorted(runtime_safe),
                                         sorted(by_layer["A"])))

    # AGENTS.md per-layer tables must equal the on-disk sets.
    tables = agents_md_tables()
    for layer in ("A", "B", "C"):
        missing = by_layer[layer] - tables[layer]
        extra = tables[layer] - by_layer[layer]
        if missing:
            problems.append("AGENTS.md Layer-%s table is MISSING rows for: %s"
                            % (layer, sorted(missing)))
        if extra:
            problems.append("AGENTS.md Layer-%s table has UNKNOWN/EXTRA rows: %s"
                            % (layer, sorted(extra)))

    # Stale count words bound to the runtime-safe core. "one"/"two" are common
    # articles and the core can't plausibly be that small, so detect from three
    # up (plus digits >=3 and multi-digit). Negative lookahead drops
    # "<n> layer(s)" so "the three layers and the runtime-safe core" is safe.
    words = [w for k, w in NUMWORDS.items() if k >= 3]
    num = "|".join(re.escape(w) for w in words) + r"|[3-9]|\d{2,}"
    pat_layer = re.compile(r"\b(%s)\s+Layer[- ]A\s+skills?\b" % num, re.I)
    pat_core = re.compile(
        r"\b(%s)\b(?!\s+layers?\b)[^.]{0,40}?runtime-safe core" % num, re.I)
    pat_core_trail = re.compile(
        r"runtime-safe core.{0,60}?\b(%s)\b(?!\s+layers?\b)[^.]{0,40}?skills?\b"
        % num, re.I)
    pats = (pat_layer, pat_core, pat_core_trail)

    # plan.md's dated journal is append-only history; do not assert it.
    SKIP_SPANS = {"plan.md": [("## Sessions", "## Backlog"),
                              ("## Next horizon", None)]}

    def skipped(doc, lines):
        out = set()
        for start, end in SKIP_SPANS.get(doc, []):
            s = next((i for i, ln in enumerate(lines)
                      if ln.startswith(start)), None)
            if s is None:
                continue
            e = next((i for i, ln in enumerate(lines[s + 1:], s + 1)
                      if end is not None and ln.startswith(end)), len(lines))
            out.update(range(s, e))
        return out

    for doc in ("AGENTS.md", "BOUNDARY.md", "README.md", "plan.md"):
        lines = (REPO / doc).read_text(encoding="utf-8").splitlines()
        skip = skipped(doc, lines)
        seen = set()
        for idx in range(len(lines)):
            if idx in skip:
                continue
            # window = this line + next non-skipped line, so a count that wraps
            # across a line break is caught while history spans stay excluded.
            window = lines[idx]
            if idx + 1 < len(lines) and (idx + 1) not in skip:
                window = window + " " + lines[idx + 1]
            for pat in pats:
                for m in pat.finditer(window):
                    found = word_to_n(m.group(1))
                    if found is None or found == n_rs:
                        continue
                    if (idx, m.group(1)) in seen:
                        continue
                    seen.add((idx, m.group(1)))
                    problems.append(
                        "%s:%d: says runtime-safe core is '%s', but %d skills "
                        "are runtime-safe:true (expected '%s'/'%d'): %r"
                        % (doc, idx + 1, m.group(1), n_rs, correct, n_rs,
                           lines[idx].strip()))

    # Inline core enumerations (a backtick run dominated by runtime-safe names,
    # e.g. BOUNDARY.md) must list every runtime-safe skill; catches a silently
    # omitted core skill independent of the count word.
    bt_run = re.compile(r"(?:`[a-z][a-z0-9-]+`(?:[,;]?\s+(?:and\s+)?)?){2,}")
    name_in = re.compile(r"`([a-z][a-z0-9-]+)`")
    for doc in ("AGENTS.md", "BOUNDARY.md", "README.md"):
        lines = (REPO / doc).read_text(encoding="utf-8").splitlines()
        skip = skipped(doc, lines)
        joined = "\n".join("" if i in skip else ln
                           for i, ln in enumerate(lines)).replace("\n", " ")
        for m in bt_run.finditer(joined):
            names = set(name_in.findall(m.group(0)))
            rs_named = names & runtime_safe
            if len(rs_named) >= 3 and len(rs_named) > len(names - runtime_safe):
                missing = runtime_safe - names
                if missing:
                    frag = m.group(0).split("`")[1]
                    ln_no = next((i + 1 for i, ln in enumerate(lines)
                                  if ("`%s`" % frag) in ln and i not in skip),
                                 "?")
                    problems.append(
                        "%s:%s: inline runtime-safe-core enumeration %s OMITS "
                        "%s (every runtime-safe:true skill must be listed)"
                        % (doc, ln_no, sorted(rs_named), sorted(missing)))

    print("runtime-safe:true skills on disk: %d (%s) -> %s"
          % (n_rs, correct, sorted(runtime_safe)))
    print("Layer sizes on disk: A=%d B=%d C=%d"
          % (len(by_layer["A"]), len(by_layer["B"]), len(by_layer["C"])))
    if problems:
        print("\nFAIL: %d doc/skill mismatch(es):" % len(problems))
        for p in problems:
            print("  - " + p)
        return 1
    print("\nOK: docs match the skills on disk "
          "(runtime-safe count + AGENTS.md layer tables consistent).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
