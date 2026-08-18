#!/usr/bin/env python3
"""draft_proposals.py — the "bubbling" pipeline: turn drift signals into DRAFT
proposals so they surface for human review.

WHY THIS EXISTS
---------------
The brain's proposal loop only moves when a proposal exists. Today proposals
are filed by hand (the [[propose]] skill). But the framework already *records*
drift in two append-only ledgers — harvest findings (memory/feedback.jsonl) and
run-log discipline flags (run_state/framework.run.jsonl, and read-only the
consumer's run log). This script reads those signals and emits a DRAFT proposal
per *new* signal, so a human reviewing the brain sees candidates bubble up
instead of having to author every proposal cold.

WHAT IT EMITS
-------------
For each new signal it appends one JSON object to memory/brain/proposals.jsonl
carrying the FILED-proposal shape (same as [[propose]]) with one difference:

    "status": "draft"        (NOT "open")

`draft` is deliberately distinct from `open`. An `open` proposal is *in review*;
a `draft` is a candidate the brain bubbled up that a human must promote to
`open` (or discard) before it enters the review-proposal loop. Fields:

    proposal_id   next sequential P-NNN
    agent_id      "draft:auto"          (so drafts are attributable, never
                                         mistaken for a human/agent filing)
    target        the framework skill the signal bears on
    target_type   "skill"
    scope         "framework"           (research/a_bgt_rsi signals are excluded)
    title, change, reasoning            derived from the signal (NO LLM call —
                                        the server lazily generates means/
                                        pros-cons cards from these fields)
    references    [<source ref>, <skill>]   the finding / run-log row it came from
    status        "draft"

VISIBILITY (coordination note — READ BEFORE WIRING DRAFTS INTO THE UI)
----------------------------------------------------------------------
brain_server.open_framework_proposals() filters proposals by their *verdict*,
keeping those whose project_summary.final_verdict(p) is in {open, human-review}.
final_verdict reads the `verdict` field of the latest lifecycle row and DEFAULTS
TO "open" when none is set. A draft is a single filing row with status="draft"
and NO `verdict` field — so final_verdict(draft) == "open".

CONSEQUENCE: with the server AS-IS, a draft WOULD leak into /api/proposals,
because the list keys off `verdict`, not `status`. This script cannot fix that
(it owns only this file). The intended end state for this slice is that drafts
do NOT appear in the open list until a follow-up explicitly opts them in. To get
there the follow-up must teach open_framework_proposals (or final_verdict) to
treat status=="draft" as a distinct, NON-open lifecycle state — e.g. skip rows
whose first entry has status "draft" unless a `?include_drafts=1` query / a
separate /api/drafts route asks for them. Until that lands, run --apply only when
a leaked draft in the open list is acceptable, or keep drafts in --dry-run.

drafts() below returns the in-file draft rows so the follow-up can surface them
(its own route) without re-deriving the signals.

SOURCES
-------
1. Harvest findings in memory/feedback.jsonl with class in
   {diverged, friction, gap} whose `skill` is a real framework skill — UNLESS
   that skill is already covered by an existing (non-draft) proposal in
   proposals.jsonl (match by skill/target). Source ref: feedback.jsonl:<H>:<ref>.
2. Drift signals in memory/brain/drift_signals.jsonl — the machine-detected
   ledger (deterministic scan + runtime self-reports) written by scan_drift.py /
   ingest_apparatus.py. Each signal whose `skill` is a real framework skill and
   is NOT already covered by an existing (non-draft) proposal bubbles to a draft.
   Source ref: the signal's own `ref` field (e.g. framework.run.jsonl:L42).

   (Run-log / schema detection used to live here as runlog_signals(); that is
   now owned by scan_drift.py and flows in via source 2, so runlog_signals() is
   no longer called from build_drafts() — see its docstring.)

IDEMPOTENCY
-----------
A second run produces no duplicates. Dedupe key is (target, source_ref): if a
draft for that pair already exists in proposals.jsonl it is skipped. The
existing-proposal coverage check (source 1) dedupes against hand-filed/agent
proposals by skill alone.

DESIGN INVARIANTS HONORED
-------------------------
- Files are canonical; this only APPENDS to proposals.jsonl, never rewrites.
- No LLM call. Card means/pros-cons are generated lazily by brain_server.py.
- Dedup-driven, so the bubble pipeline can run repeatedly (e.g. after harvest).
- Read-only on the consumer (brain firewall, BOUNDARY.md).

CLI
---
    python3 scripts/draft_proposals.py            # --dry-run (default): print
    python3 scripts/draft_proposals.py --apply    # actually append drafts

Stdlib-only. py_compile clean.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from brain_ledger import ProposalLedgerError, ProposalLedgerLock

ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / "memory" / "brain" / "proposals.jsonl"
FEEDBACK = ROOT / "memory" / "feedback.jsonl"
DRIFT_SIGNALS = ROOT / "memory" / "brain" / "drift_signals.jsonl"
SKILLS_DIR = ROOT / ".agents" / "skills"
FW_RUN = ROOT / "run_state" / "framework.run.jsonl"

# Match the filed-proposal serialization in proposals.jsonl exactly (compact
# separators, unicode preserved) so drafts are byte-compatible with the file.
_SEP = (",", ":")

DRAFT_AGENT = "draft:auto"
DRAFT_STATUS = "draft"

# Harvest finding classes that count as drift worth bubbling.
DRIFT_CLASSES = {"diverged", "friction", "gap"}
# Run-log statuses that count as a failure-ish discipline flag.
FAILURE_STATUSES = {"failed", "aborted", "escalated"}


# ---------------------------------------------------------------------------
# Loaders (absent-file / malformed-line tolerant)
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def jsonl_numbered(path: Path) -> list[tuple[int, dict]]:
    """Run-log rows with 1-based line numbers (for stable source refs)."""
    out: list[tuple[int, dict]] = []
    if not path.exists():
        return out
    with path.open() as f:
        for ln, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append((ln, obj))
    return out


def framework_skills() -> set[str]:
    """Names of the framework's skills (directories under .agents/skills with a
    SKILL.md). A signal only bubbles if its target is one of these."""
    if not SKILLS_DIR.exists():
        return set()
    return {p.name for p in SKILLS_DIR.iterdir()
            if (p / "SKILL.md").exists()}


def resolve_consumer() -> Path | None:
    """Read-only handle to the consumer apparatus, mirroring
    project_summary.resolve_consumer: $BRAIN_CONSUMER_ROOT, else a walk-up for a
    sibling a_bgt_rsi that actually holds memory/loop_memory.jsonl. None when
    not reachable (the consumer run log is then simply skipped)."""
    env = os.environ.get("BRAIN_CONSUMER_ROOT")
    if env:
        p = Path(env).expanduser()
        return p.resolve() if p.exists() else None
    cur = ROOT
    for _ in range(8):
        cand = cur / "a_bgt_rsi"
        if (cand / "memory" / "loop_memory.jsonl").exists():
            return cand.resolve()
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


# ---------------------------------------------------------------------------
# Existing-proposal state (collapse to first entry per pid; dedup indexes)
# ---------------------------------------------------------------------------

def existing_state(rows: list[dict] | None = None) -> tuple[set[str], set[tuple[str, str]], int]:
    """Returns:
      covered_skills   skills that any NON-DRAFT proposal already targets
                       (target_type=skill) — source-1 findings on these are
                       considered already covered and are skipped.
      draft_keys       {(target, source_ref)} of drafts already in the file —
                       the idempotency key.
      max_num          highest P-NNN integer seen (0 when none) — next id base.
    """
    covered_skills: set[str] = set()
    draft_keys: set[tuple[str, str]] = set()
    max_num = 0
    for r in (jsonl(PROPOSALS) if rows is None else rows):
        pid = r.get("proposal_id") or ""
        if pid.startswith("P-"):
            try:
                max_num = max(max_num, int(pid[2:]))
            except ValueError:
                pass
        # Only "filing" rows (those carrying a title) describe a target; the
        # later verdict/outcome rows omit it.
        if "title" not in r:
            continue
        status = (r.get("status") or "").strip()
        target = (r.get("target") or "").strip()
        if status == DRAFT_STATUS:
            for ref in (r.get("references") or []):
                if isinstance(ref, str):
                    draft_keys.add((target, ref))
        elif (r.get("target_type") or "").strip() == "skill" and target:
            # An open/closed/human-review proposal already speaks to this skill.
            covered_skills.add(target)
    return covered_skills, draft_keys, max_num


# ---------------------------------------------------------------------------
# Signal -> draft proposal payload (no id yet; assigned at emit time)
# ---------------------------------------------------------------------------

def _trim(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


# A skill name quoted in backticks/quotes or written as a [[wikilink]].
_NAMED_SKILL_RE = re.compile(
    r"[`'\"]([a-z][a-z0-9-]{2,})[`'\"]|\[\[([a-z][a-z0-9-]{2,})\]\]")


def _harvest_num(hid) -> int | None:
    """Numeric part of a harvest id, e.g. 'H008' -> 8. None when unparseable."""
    m = re.match(r"H0*(\d+)", str(hid or "").strip())
    return int(m.group(1)) if m else None


def last_clean_harvest(skills: set[str]) -> dict[str, int]:
    """{skill: highest harvest number at which the skill was CLEAN}, where a
    harvest is clean for a skill iff it carried a 'confirmed' finding on it AND no
    open (friction/gap/diverged) finding on it.

    Used to suppress superseded findings: a CLEAN harvest LATER than a finding is
    the framework's own conformance evidence that the skill is sound again, so the
    earlier friction/gap is resolved and should not bubble. The clean test is the
    whole point — a harvest that BOTH confirms and re-flags a skill (e.g. fallback /
    repro-check at H008) is NOT clean, so its still-open findings keep bubbling.
    Permanent-safe: a skill whose latest harvest re-opens it has no (or only an
    earlier) clean watermark, and a finding newer than the watermark still bubbles."""
    confirmed: dict[str, set[int]] = {}
    opened: dict[str, set[int]] = {}
    for f in jsonl(FEEDBACK):
        skill = (f.get("skill") or "").strip()
        if skill not in skills:
            continue
        hn = _harvest_num(f.get("harvest_id"))
        if hn is None:
            continue
        cls = (f.get("class") or "").strip()
        if cls == "confirmed":
            confirmed.setdefault(skill, set()).add(hn)
        elif cls in DRIFT_CLASSES:
            opened.setdefault(skill, set()).add(hn)
    out: dict[str, int] = {}
    for skill, conf_hns in confirmed.items():
        clean = [h for h in conf_hns if h not in opened.get(skill, set())]
        if clean:
            out[skill] = max(clean)
    return out


def proposes_existing_skill(text: str, skills: set[str]) -> str | None:
    """If `text` proposes creating a NEW skill that already exists, return that
    skill's name; else None — the resolved-finding guard.

    A finding whose remedy already shipped is stale and must not be re-bubbled
    (e.g. an H002 "new skill 'decision-log'" gap once decision-log exists, or the
    slip-ladder gap once slip-ladder exists). Precise by design: it fires only when
    the text *explicitly proposes a new skill* ("new skill" …) and the FIRST named
    token after that phrase — in quotes, backticks, or a [[wikilink]] — is an
    actual existing skill. Taking only the first named token (the one being
    proposed) avoids over-firing when a genuinely-new skill's finding merely quotes
    an existing skill's name elsewhere."""
    low = text.lower()
    idx = low.find("new skill")
    if idx < 0:
        return None
    m = _NAMED_SKILL_RE.search(text, idx)
    if not m:
        return None
    name = m.group(1) or m.group(2)
    return name if name in skills else None


def harvest_signals(skills: set[str],
                    covered_skills: set[str]) -> tuple[list[dict], list[dict]]:
    """Source 1 — one candidate per (skill, harvest_id, ref) drift finding on a
    framework skill not already covered by an existing proposal.

    Returns (candidates, resolved). `resolved` carries findings skipped because
    their remedy already shipped (they propose a 'new skill' that now exists);
    each is {target, source_ref, reason} so the bubbler reports them rather than
    dropping them silently."""
    out: list[dict] = []
    resolved: list[dict] = []
    seen: set[tuple[str, str]] = set()
    clean_after = last_clean_harvest(skills)
    for f in jsonl(FEEDBACK):
        cls = (f.get("class") or "").strip()
        skill = (f.get("skill") or "").strip()
        if cls not in DRIFT_CLASSES or skill not in skills:
            continue
        if skill in covered_skills:
            continue
        hid = (f.get("harvest_id") or "?").strip()
        ref = (f.get("ref") or "").strip()
        source_ref = f"feedback.jsonl:{hid}:{ref}" if ref else f"feedback.jsonl:{hid}"
        key = (skill, source_ref)
        if key in seen:
            continue
        seen.add(key)
        evidence = (f.get("evidence") or "").strip()
        plan = (f.get("plan_candidate") or "").strip()
        # Resolved-finding guard #1: skip a finding whose proposed remedy (a new
        # skill) already exists. Precise — checks actual skill existence — and
        # does NOT suppress future real findings on existing skills.
        shipped = proposes_existing_skill(f"{plan} {evidence}", skills)
        if shipped:
            resolved.append({"target": skill, "source_ref": source_ref,
                             "reason": f"resolved (skill '{shipped}' exists)"})
            continue
        # Resolved-finding guard #2: skip a finding superseded by a CLEAN harvest
        # (one that confirmed the skill AND carried no open finding on it) LATER
        # than this finding. Permanent-safe: a skill re-opened at its latest
        # harvest has no qualifying clean watermark, so its still-open findings —
        # e.g. fallback / repro-check at H008 — keep bubbling.
        fin_num = _harvest_num(hid)
        clean_h = clean_after.get(skill)
        if fin_num is not None and clean_h is not None and clean_h > fin_num:
            resolved.append({
                "target": skill, "source_ref": source_ref,
                "reason": (f"superseded (skill clean at H{clean_h:03d} — confirmed, "
                           f"no open finding — > finding H{fin_num:03d})")})
            continue
        title = f"[{cls}] {skill}: {_trim(plan or evidence, 90)}"
        change = (plan or f"Address the {cls} signal on [[{skill}]]: {evidence}")
        reasoning = (
            f"Harvest {hid} flagged a '{cls}' signal on the [[{skill}]] skill "
            f"({f.get('source', 'consumer')} trace, ref {ref or 'n/a'}). "
            f"Evidence: {evidence} Bubbled as a DRAFT for human triage — "
            "promote to 'open' to enter review, or discard."
        )
        out.append({
            "target": skill,
            "title": _trim(title, 140),
            "change": change,
            "reasoning": reasoning,
            "source_ref": source_ref,
        })
    return out, resolved


def signal_candidates(skills: set[str],
                      covered_skills: set[str]) -> list[dict]:
    """Source 2 — one candidate per drift signal in drift_signals.jsonl (the
    machine-detected ledger: deterministic scan + runtime self-reports) on a
    framework skill not already covered by an existing proposal. Mirrors the
    shape harvest_signals returns; the signal's own `ref` is the source_ref so
    the existing (target, source_ref) dedup keeps it idempotent."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for s in jsonl(DRIFT_SIGNALS):
        skill = (s.get("skill") or "").strip()
        if skill not in skills or skill in covered_skills:
            continue
        source_ref = (s.get("ref") or "").strip()
        if not source_ref:
            continue
        key = (skill, source_ref)
        if key in seen:
            continue
        seen.add(key)
        sid = (s.get("signal_id") or "?").strip()
        detector = (s.get("detector") or "signal").strip()
        source = (s.get("source") or "scan").strip()
        observed = (s.get("status_observed") or "").strip()
        evidence = (s.get("evidence") or "").strip()
        title = f"[{detector}] {skill}: {_trim(evidence, 90)}"
        change = (
            f"Address the drift signal on [[{skill}]] "
            f"({detector}, {observed or 'n/a'}): {evidence}"
        )
        reasoning = (
            f"Drift signal {sid} ({detector}, source '{source}') flagged the "
            f"[[{skill}]] skill"
            + (f" with status_observed='{observed}'" if observed else "")
            + f". Ref {source_ref}. Evidence: {evidence} "
            "Bubbled as a DRAFT for human triage — promote to 'open' to enter "
            "review, or discard."
        )
        out.append({
            "target": skill,
            "title": _trim(title, 140),
            "change": change,
            "reasoning": reasoning,
            "source_ref": source_ref,
        })
    return out


def runlog_signals(skills: set[str],
                   consumer: Path | None) -> list[dict]:
    """SUPERSEDED — no longer called from build_drafts(); scan_drift.py now owns
    run-log/schema detection and feeds it in via signal_candidates() reading
    drift_signals.jsonl. Left defined (not wired) to avoid double-bubbling the
    same run-log rows. One candidate per run-log row with skill_used on a
    framework skill AND a failure-ish status, across the framework run log and
    (read-only) the consumer's run log if reachable."""
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    logs: list[tuple[str, Path]] = [("framework.run.jsonl", FW_RUN)]
    if consumer is not None:
        logs.append(("a_bgt_rsi/week1.run.jsonl",
                     consumer / "run_state" / "week1.run.jsonl"))
    for label, path in logs:
        for ln, o in jsonl_numbered(path):
            skill = (o.get("skill_used") or "").strip()
            status = (o.get("status") or "").strip()
            if skill not in skills or status not in FAILURE_STATUSES:
                continue
            source_ref = f"{label}:L{ln}"
            key = (skill, source_ref)
            if key in seen:
                continue
            seen.add(key)
            task = (o.get("task_id") or "(untitled step)").strip()
            expected = (o.get("observable_expected") or "").strip()
            actual = (o.get("observable_actual") or "").strip()
            notes = (o.get("notes") or "").strip()
            detail = actual or notes or expected
            title = f"[run:{status}] {skill}: {_trim(task, 80)}"
            change = (
                f"Investigate the {status} run of [[{skill}]] at {source_ref} "
                f"(task '{task}') and decide whether the skill's guidance needs "
                "tightening so this failure mode is caught or avoided."
            )
            reasoning = (
                f"Run-log row {source_ref} recorded skill_used={skill} with "
                f"status='{status}' (a failure-ish discipline flag). "
                f"Task: {task}. {('Observed: ' + detail) if detail else ''} "
                "Bubbled as a DRAFT for human triage — promote to 'open' to "
                "enter review, or discard."
            ).strip()
            out.append({
                "target": skill,
                "title": _trim(title, 140),
                "change": change,
                "reasoning": reasoning,
                "source_ref": source_ref,
            })
    return out


# ---------------------------------------------------------------------------
# Build draft entries (assign sequential ids, dedup against existing drafts)
# ---------------------------------------------------------------------------

def build_drafts(rows: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """Returns (new_drafts, skipped) — skipped carries {target, source_ref,
    reason} so the summary can explain idempotency no-ops."""
    skills = framework_skills()
    covered_skills, draft_keys, max_num = existing_state(rows)

    # NOTE: runlog_signals() is intentionally NOT called here — scan_drift.py
    # owns run-log/schema detection and its findings arrive via the
    # drift_signals.jsonl ledger that signal_candidates() reads. Calling both
    # would double-bubble the same run-log rows.
    harvest_cands, resolved = harvest_signals(skills, covered_skills)
    candidates = harvest_cands + signal_candidates(skills, covered_skills)

    new_drafts: list[dict] = []
    skipped: list[dict] = list(resolved)  # resolved-finding skips, reported not silent
    minted_keys: set[tuple[str, str]] = set()
    ts = _now()
    n = max_num
    for c in candidates:
        key = (c["target"], c["source_ref"])
        if key in draft_keys or key in minted_keys:
            skipped.append({"target": c["target"], "source_ref": c["source_ref"],
                            "reason": "already drafted"})
            continue
        minted_keys.add(key)
        n += 1
        new_drafts.append({
            "timestamp": ts,
            "proposal_id": f"P-{n:03d}",
            "agent_id": DRAFT_AGENT,
            "title": c["title"],
            "target_type": "skill",
            "target": c["target"],
            "scope": "framework",
            "change": c["change"],
            "reasoning": c["reasoning"],
            "references": [c["source_ref"], c["target"]],
            "status": DRAFT_STATUS,
        })
    return new_drafts, skipped


def drafts() -> list[dict]:
    """All draft-status proposals currently in proposals.jsonl. Exposed so a
    follow-up can opt the UI into surfacing drafts without re-deriving them."""
    return [r for r in jsonl(PROPOSALS)
            if (r.get("status") or "").strip() == DRAFT_STATUS and "title" in r]


# ---------------------------------------------------------------------------
# Emit + CLI
# ---------------------------------------------------------------------------

def append_drafts(rows: list[dict]) -> None:
    """Append already-minted drafts through the shared lock.

    This compatibility surface is intentionally narrow.  The CLI uses
    ``apply_drafts`` below so id allocation and dedupe happen *inside* the same
    lock, rather than minting rows from a stale snapshot and then appending them.
    """
    with ProposalLedgerLock(PROPOSALS) as ledger:
        ledger.append(rows)


def apply_drafts() -> tuple[list[dict], list[dict]]:
    """Atomically derive, deduplicate, allocate IDs, and append draft rows.

    The source signal ledgers are read-only inputs.  The proposal snapshot used
    for suppression and numbering is read only while the proposal-ledger lock is
    held, eliminating races between simultaneous ``--apply`` invocations.
    """
    with ProposalLedgerLock(PROPOSALS) as ledger:
        new_drafts, skipped = build_drafts(ledger.rows)
        ledger.append(new_drafts)
        return new_drafts, skipped


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Bubble drift signals (harvest findings + run-log flags) "
                    "into DRAFT proposals in memory/brain/proposals.jsonl.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="print what would be added; write nothing (default).")
    mode.add_argument("--apply", action="store_true",
                      help="actually append the draft proposals.")
    args = ap.parse_args()
    apply = bool(args.apply)

    try:
        if apply:
            new_drafts, skipped = apply_drafts()
        else:
            # Dry run intentionally does not create a lock file or write any
            # bytes.  It is an informational, non-authoritative preview.
            new_drafts, skipped = build_drafts()
    except ProposalLedgerError as e:
        print(f"  REFUSED — proposal ledger is not safe to write: {e}", file=sys.stderr)
        return 2

    print("draft_proposals — bubble drift signals into DRAFT proposals")
    print(f"  proposals file: {PROPOSALS}")
    print(f"  candidates: {len(new_drafts) + len(skipped)}  "
          f"new: {len(new_drafts)}  skipped: {len(skipped)}")
    for d in new_drafts:
        print(f"  + {d['proposal_id']}  skill:{d['target']}  "
              f"<- {d['references'][0]}")
        print(f"      {d['title']}")
    if not new_drafts:
        print("  (no new signals to bubble)")
    # Surface guard skips (resolved-finding + superseded) rather than hiding them
    # — a silent drop would read as "nothing to bubble" when it isn't.
    guard_skips = [s for s in skipped
                   if str(s.get("reason", "")).startswith(("resolved", "superseded"))]
    if guard_skips:
        print(f"  not bubbled — remedy already shipped or superseded by a later "
              f"confirmation: {len(guard_skips)}")
        for s in guard_skips:
            print(f"    · skill:{s['target']}  {s['reason']}  <- {s['source_ref']}")

    if apply:
        if new_drafts:
            print(f"  APPLIED — appended {len(new_drafts)} draft(s) "
                  f"with status='{DRAFT_STATUS}'.")
        else:
            print("  APPLIED — nothing to append.")
    else:
        print("  DRY RUN — nothing written. Re-run with --apply to append.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
