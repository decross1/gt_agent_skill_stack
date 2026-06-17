#!/usr/bin/env python3
"""project_summary.py — project the brain's governance/skills/memory layer into
the schema-v2 `summary.json` + `summary_data.js` consumed by dashboard.html.

This is the NARRATIVE BRIEFING projector, distinct from `project_pages.py`
(which emits the GRAPH's per-entity pages + index.json). It reads the same
canonical sources through the same side-effect-free loaders imported from
`project_pages` and emits ONE object — `window.BRAIN_SUMMARY` — whose shape is
the single source of truth between this generator and the page:

  schema_version=2, generated_at, repo, consumer, window,
  status_strip, inbox, agents, skills, matrix, contracts, loop,
  timeline, incidents, rules, attribution, days

Core ideas of v2 (vs the v1 three-act layout):
  - the ATTRIBUTION LADDER: one attribution per run-log row, strict
    precedence (explicit skill_used > status-semantics > task_id pattern),
    plus harvest findings (→ nara) and spawn-contract skill subsets — every
    matrix cell carries per-method counts so explicit never blurs into
    inferred.
  - the NEEDS-YOU INBOX: everything awaiting a human (pending gates, open
    proposals, drift, unverified contracts, stale runs), each with the exact
    resolve command (gate items use the gate_cli form from the consumer's
    ui/backend/human_todo.py).
  - WINDOWING: timeline + by_day buckets are trailing `max_days` anchored on
    the newest observed event date (data-anchored, so reruns on a quiet day
    are no-ops); inbox and governance are NOT windowed.

Stdlib-only. Deterministic + idempotent: compare-before-write excludes
`generated_at`, so a rerun with unchanged inputs touches nothing. Read-only
on the consumer (brain firewall). Consumer resolution: $BRAIN_CONSUMER_ROOT
if set, else a walk-up search for a sibling `a_bgt_rsi` that contains
memory/loop_memory.jsonl — never `REPO.parent` blindly (worktrees would
resolve to a void).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date as date_cls, datetime, timedelta, timezone
from pathlib import Path

# Side-effect-free parsers + framework path constants from project_pages so the
# two projectors read the same sources through the same code (its main() is
# __main__-guarded; importing runs only constant/regex assignment). Consumer
# paths are NOT imported — project_pages derives them from REPO.parent, which
# is wrong inside a git worktree; resolve_consumer() below is authoritative.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from project_pages import (  # noqa: E402
    REPO,
    PROPOSALS,
    FEEDBACK,
    SPAWN_LEDGER,
    FW_DECISIONS,
    load_jsonl,
    load_skills,
    load_rules,
    load_decisions,
    slugify,
)

SCHEMA_VERSION = 2
VIEW_DIR = REPO / "memory" / "brain" / "view"
NARRATIVES = REPO / "memory" / "brain" / "narratives.jsonl"
CONFORMANCE = REPO / "memory" / "conformance.md"
FW_RUN = REPO / "run_state" / "framework.run.jsonl"
SKILLS_DIR = REPO / ".agents" / "skills"

WINDOW_DEFAULT_DAYS = 7
WINDOW_MIN_DAYS = 1
WINDOW_MAX_DAYS = 7

# D-042 (a_bgt_rsi/DECISIONS.md): these four are intentionally REFERENCED-ONLY
# in the consumer — harvest must not re-flag them as unused.
BY_DESIGN = {"orchestrate", "experiment", "repro-check", "plan-research"}

# Exact resolve-command form from a_bgt_rsi/ui/backend/human_todo.py
# (_GATE_RESOLVE_TEMPLATE) — the sanctioned write-back channel for gates.
GATE_CLI = (
    ".venv-chroma/bin/python -m orchestrator.gate_cli "
    "--iteration-id {iteration_id} --verdict <valid|invalid|needs_revision> "
    "--note '<why>'"
)
STALE_RUN_AFTER_MIN = 30

# Attribution ladder rung 2 — status semantics. A run-log row with one of
# these statuses (and no explicit skill_used) is governed by the named skill.
STATUS_TO_SKILL = {
    "failed": "validate",
    "partial_pass": "validate",
    "aborted": "validate",
    "recovered": "validate",
    "escalated": "fallback",
    "human_gate_blocked": "gate-check",
    "gate_armed": "gate-check",
    "declared": "slip-ladder",
}
# Statuses that also flag the row in the timeline lane (observed deviations).
FLAG_STATUSES = set(STATUS_TO_SKILL)

# Canonical run-log agents → page hue var + kind. Unknown agents get a
# slug-derived var so the page can still color them deterministically.
AGENT_HUES = {
    "claude-code-main": "--agent-claude",
    "nara": "--agent-nara",
    "coordinator": "--agent-coordinator",
    "workflow": "--agent-workflow",
    "primary-session/integrator": "--agent-integrator",
    "human:decross1": "--agent-human",
}
RUNTIME_AGENTS = {"nara", "coordinator"}  # the consumer's own deployed actors


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def resolve_consumer() -> Path | None:
    """$BRAIN_CONSUMER_ROOT, else walk up from REPO looking for a sibling
    a_bgt_rsi that actually contains memory/loop_memory.jsonl."""
    env = os.environ.get("BRAIN_CONSUMER_ROOT")
    if env:
        p = Path(env).expanduser()
        return p.resolve() if p.exists() else None
    cur = REPO
    for _ in range(8):
        cand = cur / "a_bgt_rsi"
        if (cand / "memory" / "loop_memory.jsonl").exists():
            return cand.resolve()
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _date_of(iso: str | None) -> str:
    return (iso or "")[:10]


def _parse_date(d: str) -> date_cls | None:
    try:
        return date_cls.fromisoformat(d[:10])
    except (ValueError, TypeError):
        return None


def _days_between(older: str, newer: str) -> int | None:
    a, b = _parse_date(older), _parse_date(newer)
    if a is None or b is None:
        return None
    return (b - a).days


def _trim(s: str | None, n: int = 100) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def agent_hue(agent_id: str) -> str:
    return AGENT_HUES.get(agent_id, "--agent-" + slugify(agent_id))


def agent_kind(agent_id: str) -> str:
    if agent_id.startswith("human:"):
        return "human"
    if agent_id in RUNTIME_AGENTS or "nemoclaw" in agent_id:
        return "runtime"
    return "dev"


def canon_runlog_agent(raw: str | None, default: str) -> tuple[str, bool]:
    """(canonical agent, explicit?) for a run-log row. Workflow limb labels
    (workflow:wf_xxx/limb-a) collapse to 'workflow'; nara sub-labels to
    'nara'; empty falls to the per-file default (FR-003 canonicalization)."""
    r = (raw or "").strip()
    if not r:
        return default, False
    if r.startswith("workflow:") or r == "workflow":
        return "workflow", True
    if r == "nara" or r.startswith("nara:") or r.startswith("nara."):
        return "nara", True
    return r, True


def load_runlog(path: Path) -> list[tuple[int, dict]]:
    """Run-log rows with line numbers (for source refs). Absent-file tolerant."""
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


def collapse_proposals(rows: list[dict]) -> dict[str, dict]:
    """{pid: {first, latest, lifecycle[]}} — lifecycle time-ordered; the last
    row's verdict is the proposal's current verdict ('open' if never set)."""
    by_pid: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda x: x.get("timestamp", "")):
        pid = r.get("proposal_id")
        if pid:
            by_pid.setdefault(pid, []).append(r)
    return {pid: {"first": h[0], "latest": h[-1], "lifecycle": h}
            for pid, h in by_pid.items()}


def final_verdict(p: dict) -> str:
    return p["latest"].get("verdict") or "open"


def lifecycle_state(p: dict) -> str:
    """draft | open | human-review | closed — the proposal's LANE (distinct from
    its raw verdict). A 'draft' is a bubbled candidate (status=='draft' on its
    latest row, no verdict yet) that is NOT in review; a promotion row (status
    'open', or a verdict) moves it out of the draft lane. Keys off the LATEST row
    so an append-only promotion flips draft→open without rewriting the draft.

    This is the authority for 'is this proposal in the open review queue?' —
    final_verdict alone can't tell a draft from an open proposal (both have no
    verdict), which is why a draft would otherwise leak into the inbox."""
    latest = p["latest"]
    if latest.get("verdict"):
        return "human-review" if latest["verdict"] == "human-review" else "closed"
    if (latest.get("status") or "").strip() == "draft":
        return "draft"
    return "open"


def proposal_scope(first: dict, consumer_name: str | None) -> str:
    """Classify a proposal as 'framework' (this agent_system — skills, brain
    tooling, framework rules/disciplines) or 'research' (the consumer
    apparatus — its code, tests, UI, runtime).

    An explicit `scope` field on the proposal wins. Otherwise infer from the
    change site: a proposal whose `target` names the consumer apparatus is
    research-scoped; everything else is framework-scoped.

    The brain UI surfaces and resolves only framework-scoped proposals;
    research-scoped ones belong to the consumer's own process and are filtered
    out of the needs-you inbox and the framework's proposal loop stats."""
    explicit = (first.get("scope") or "").strip().lower()
    if explicit in ("framework", "research"):
        return explicit
    target = (first.get("target") or "").strip().lower()
    if consumer_name and consumer_name.lower() in target:
        return "research"
    return "framework"


# ---------------------------------------------------------------------------
# conformance.md per-skill table (parse-failure tolerant)
# ---------------------------------------------------------------------------

_CONF_ROW = re.compile(
    r"^\|\s*([a-z][a-z0-9-]*)\s*\|\s*([ABC?])\s*\|\s*([0-9—-]+)\s*\|\s*([0-9—-]+)"
    r"\s*\|\s*([0-9—-]+)\s*\|\s*([0-9—-]+)\s*\|\s*([^|]+)\|?\s*$",
    re.MULTILINE,
)


def parse_conformance() -> dict[str, dict]:
    """Per-skill rows of the '## Per-skill conformance' table. Returns {} on
    any failure — callers fall back to feedback.jsonl classes only."""
    out: dict[str, dict] = {}
    try:
        text = CONFORMANCE.read_text()
    except OSError:
        return out

    def _n(cell: str) -> int:
        cell = cell.strip()
        return int(cell) if cell.isdigit() else 0

    try:
        for m in _CONF_ROW.finditer(text):
            name, _layer, conf, fric, gap, div, status = m.groups()
            out[name] = {
                "confirmed": _n(conf), "friction": _n(fric),
                "gap": _n(gap), "diverged": _n(div),
                "status": " ".join(status.split()),
            }
    except Exception:  # noqa: BLE001 — tolerance is the contract here
        return {}
    return out


_BORN_CACHE: dict[str, str | None] = {}


def skill_born_date(name: str) -> str | None:
    """First-commit date of the skill's SKILL.md (git --diff-filter=A,
    --follow; last line = the original add). None when git is unavailable."""
    if name in _BORN_CACHE:
        return _BORN_CACHE[name]
    born: str | None = None
    try:
        res = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%cs", "--follow",
             "--", f".agents/skills/{name}/SKILL.md"],
            cwd=REPO, capture_output=True, text=True, timeout=20,
        )
        lines = [l for l in res.stdout.strip().splitlines() if l.strip()]
        if res.returncode == 0 and lines:
            born = lines[-1].strip()
    except (OSError, subprocess.SubprocessError):
        born = None
    _BORN_CACHE[name] = born
    return born


# ---------------------------------------------------------------------------
# Attribution ladder (matrix + agents + skill usage all derive from this)
# ---------------------------------------------------------------------------

def _review_or_propose(task: str) -> str:
    return "review-proposal" if "review" in task else "propose"


def ladder_attribution(obj: dict) -> tuple[str | None, str | None]:
    """(skill, method) for one run-log row — rungs 1-3 of the ladder.
    method ∈ {skill_used, status, task}; (None, None) when no rung matches."""
    sk = (obj.get("skill_used") or "").strip()
    if sk:
        return sk, "skill_used"
    st = (obj.get("status") or "").strip()
    if st in STATUS_TO_SKILL:
        return STATUS_TO_SKILL[st], "status"
    task = (obj.get("task_id") or "").strip()
    if task:
        if task.startswith("gate."):
            return "gate-check", "task"
        if "harvest" in task:
            return "harvest", "task"
        if "validate" in task:
            return "validate", "task"
        if task.startswith("sp_") or "spawn" in task:
            return "spawn-contract", "task"
        if "proposal" in task:
            return _review_or_propose(task), "task"
    return None, None


def build_run_attributions(
    week1_rows: list[tuple[int, dict]],
    fw_rows: list[tuple[int, dict]],
) -> list[dict]:
    """One record per run-log row: {agent, explicit_agent, skill, method,
    date, ts, file, line, status, task}. skill/method None when no rung hit."""
    out: list[dict] = []
    for default, fname, rows in (
        ("nara", "week1.run.jsonl", week1_rows),
        ("claude-code-main", "framework.run.jsonl", fw_rows),
    ):
        for ln, o in rows:
            agent, explicit_agent = canon_runlog_agent(o.get("agent"), default)
            skill, method = ladder_attribution(o)
            ts = o.get("timestamp") or ""
            out.append({
                "agent": agent, "explicit_agent": explicit_agent,
                "skill": skill, "method": method,
                "date": _date_of(ts), "ts": ts, "file": fname, "line": ln,
                "status": o.get("status"), "task": o.get("task_id") or "",
                "fallback_taken": bool(o.get("fallback_taken")),
            })
    return out


# ---------------------------------------------------------------------------
# Contracts (both spawn ledgers, collapsed per spawn_id)
# ---------------------------------------------------------------------------

def _contract_agent(spawn_id: str, surface: str) -> str:
    # SP-wf* children are the named workflow limbs (their run-log rows carry
    # workflow:* agents); other children are anonymous one-shot subagents of
    # the dev session that spawned them.
    if spawn_id.startswith("SP-wf"):
        return "workflow"
    return "claude-code-main" if surface == "framework" else "nara"


def normalize_done_check(status: str, raw: str | None) -> str:
    if status == "spawned":
        return "pending"
    text = (raw or "").strip()
    if text in ("pass", "fail", "inconclusive"):
        return text
    if text:
        return "freeform"
    return "unverified"


def build_contracts(consumer: Path | None, today: str) -> list[dict]:
    rows: list[tuple[str, dict]] = [("framework", r) for r in load_jsonl(SPAWN_LEDGER)]
    if consumer is not None:
        ap_ledger = consumer / "run_state" / "spawn.jsonl"
        rows += [("apparatus", r) for r in load_jsonl(ap_ledger)]

    first: dict[str, tuple[str, dict]] = {}
    latest: dict[str, tuple[str, dict]] = {}
    for surface, r in sorted(rows, key=lambda x: x[1].get("timestamp", "")):
        sid = r.get("spawn_id")
        if not sid:
            continue
        first.setdefault(sid, (surface, r))
        latest[sid] = (surface, r)

    out: list[dict] = []
    for sid, (surface, first_row) in first.items():
        latest_row = latest[sid][1]
        contract = first_row.get("contract") or {}
        status = latest_row.get("status", "?")
        raw_check = ((latest_row.get("result") or {}).get("done_condition_check"))
        date = _date_of(first_row.get("timestamp"))
        out.append({
            "spawn_id": sid,
            "surface": surface,
            "date": date,
            "status": status,
            "agent": _contract_agent(sid, surface),
            "task": first_row.get("child_task_id")
                    or _trim(contract.get("task_statement"), 80),
            "done_check": normalize_done_check(status, raw_check),
            "done_check_raw": (raw_check or None),
            "skill_subset": list(contract.get("skill_subset") or []),
            "authority_cap": _trim(contract.get("authority_cap"), 200) or None,
            "budget": contract.get("budget") or {},
            "age_days": _days_between(date, today),
        })
    out.sort(key=lambda c: (c["date"], c["spawn_id"]), reverse=True)
    return out


# ---------------------------------------------------------------------------
# Agents + matrix
# ---------------------------------------------------------------------------

def build_agents_and_matrix(
    run_attr: list[dict],
    feedback_rows: list[dict],
    contracts: list[dict],
    human_actions: list[tuple[str, str]],   # (ts, human_agent_id)
    skill_names: set[str],
    win_start: str,
    win_end: str,
) -> tuple[list[dict], dict, list[dict]]:
    """Returns (agents, matrix, all_attributions). all_attributions = run-log
    rung hits + harvest rows (→ nara) + contract skill subsets — the matrix's
    raw material; skills[].usage sums the same records per skill."""
    attributions: list[dict] = []
    for a in run_attr:
        if a["skill"] and a["skill"] in skill_names:
            attributions.append({
                "agent": a["agent"], "skill": a["skill"],
                "method": a["method"], "date": a["date"],
                "explicit": a["method"] == "skill_used",
            })
    # rung 4 — every harvest finding evidences nara exercising that skill
    for f in feedback_rows:
        sk = (f.get("skill") or "").strip()
        if sk in skill_names:
            attributions.append({
                "agent": "nara", "skill": sk, "method": "harvest",
                "date": f.get("date") or "", "explicit": False,
            })
    # rung 5 — a spawn contract's skill_subset is referenced-authority for the
    # child agent (weak evidence: authorization, not observed use)
    for c in contracts:
        for sk in c["skill_subset"]:
            if sk in skill_names:
                attributions.append({
                    "agent": c["agent"], "skill": sk, "method": "contract",
                    "date": c["date"], "explicit": False,
                })

    # --- agents -----------------------------------------------------------
    seen: dict[str, dict] = {}

    def _touch(agent: str, ts: str, explicit: bool):
        rec = seen.setdefault(agent, {
            "first": ts or "9999", "last": ts or "",
            "explicit": 0, "default": 0, "by_day": Counter(),
        })
        if ts:
            rec["first"] = min(rec["first"], ts)
            rec["last"] = max(rec["last"], ts)
        rec["explicit" if explicit else "default"] += 1
        d = _date_of(ts)
        if win_start <= d <= win_end:
            rec["by_day"][d] += 1

    for a in run_attr:
        _touch(a["agent"], a["ts"], a["explicit_agent"])
    for ts, who in human_actions:
        _touch(who, ts, True)

    agents: list[dict] = []
    for aid, rec in seen.items():
        if rec["explicit"] and rec["default"]:
            evidence = "mixed"
        elif rec["explicit"]:
            evidence = "explicit"
        else:
            evidence = "inferred"
        agents.append({
            "id": aid,
            "kind": agent_kind(aid),
            "hue": agent_hue(aid),
            "first_seen": _date_of(rec["first"]) if rec["first"] != "9999" else None,
            "last_seen": _date_of(rec["last"]) or None,
            "runs_by_day": {d: rec["by_day"][d] for d in sorted(rec["by_day"])},
            "evidence": evidence,
        })
    agents.sort(key=lambda a: (-(sum(a["runs_by_day"].values())), a["id"]))

    # --- matrix -----------------------------------------------------------
    cells: dict[tuple[str, str], dict] = {}
    for at in attributions:
        key = (at["agent"], at["skill"])
        cell = cells.setdefault(key, {
            "agent": at["agent"], "skill": at["skill"],
            "explicit": 0, "inferred": 0,
            "methods": {"skill_used": 0, "status": 0, "task": 0,
                        "harvest": 0, "contract": 0},
            "by_day": defaultdict(lambda: {"e": 0, "i": 0}),
            "last": "",
        })
        cell["explicit" if at["explicit"] else "inferred"] += 1
        cell["methods"][at["method"]] += 1
        cell["last"] = max(cell["last"], at["date"])
        if win_start <= at["date"] <= win_end:
            cell["by_day"][at["date"]]["e" if at["explicit"] else "i"] += 1

    cell_list = []
    for (_, _), c in sorted(cells.items()):
        c["by_day"] = {d: c["by_day"][d] for d in sorted(c["by_day"])}
        c["last"] = c["last"] or None
        cell_list.append(c)
    matrix = {
        "cells": cell_list,
        "method_note": (
            "one attribution per run-log row, strict ladder: explicit "
            "skill_used > status-semantics > task_id pattern; plus harvest "
            "findings (→ nara) and spawn-contract skill subsets — those two "
            "and the lower rungs are INFERRED. e=explicit, i=inferred; "
            "by_day buckets cover the trailing window only."
        ),
    }
    return agents, matrix, attributions


# ---------------------------------------------------------------------------
# Skills + governance
# ---------------------------------------------------------------------------

def build_skills(
    skills_meta: list[dict],
    feedback_rows: list[dict],
    conformance: dict[str, dict],
    proposals: dict[str, dict],
    rules: list[dict],
    attributions: list[dict],
    win_start: str,
    win_end: str,
) -> tuple[list[dict], list[dict]]:
    """Returns (skills, firewall_violations)."""
    drift_evidence: dict[str, Counter] = defaultdict(Counter)
    drift_latest: dict[str, str] = {}
    confirmed: Counter = Counter()
    for f in feedback_rows:
        sk, cls = (f.get("skill") or "").strip(), f.get("class") or ""
        if not sk:
            continue
        if cls in ("friction", "gap", "diverged"):
            drift_evidence[sk][cls] += 1
            drift_latest[sk] = max(drift_latest.get(sk, ""), f.get("date") or "")
        elif cls == "confirmed":
            confirmed[sk] += 1

    # healed: accepted proposal targeting an existing skill, or a rule whose
    # body extends [[skill]] (FR-002 → resume-state). "New skill" proposals
    # (title says so) are births, not healings.
    new_skill_re = re.compile(r"\bnew\b.{0,40}\bskill\b", re.IGNORECASE)
    extends_re = re.compile(r"extends\s+(?:the\s+)?\[\[([a-z0-9-]+)\]\]")
    healed_by: dict[str, dict] = {}
    born_via: dict[str, str] = {}
    for pid, p in proposals.items():
        if final_verdict(p) not in ("accepted", "auto-accept"):
            continue
        first = p["first"]
        if (first.get("target_type") or "").strip() != "skill":
            continue
        target = (first.get("target") or "").strip()
        accepted_at = _date_of(p["latest"].get("timestamp"))
        if new_skill_re.search(first.get("title") or ""):
            born_via[target] = pid
            continue
        healed_by[target] = {"proposal_id": pid, "accepted_at": accepted_at,
                             "rule_id": None}
    for r in rules:
        m = extends_re.search(r.get("body", ""))
        if m and m.group(1) not in healed_by:
            healed_by[m.group(1)] = {"proposal_id": None,
                                     "accepted_at": r.get("date") or None,
                                     "rule_id": r["rule_id"]}

    usage: dict[str, dict] = defaultdict(lambda: {"explicit": 0, "inferred": 0,
                                                  "last_used": "",
                                                  "non_contract": 0})
    for at in attributions:
        u = usage[at["skill"]]
        u["explicit" if at["explicit"] else "inferred"] += 1
        u["last_used"] = max(u["last_used"], at["date"])
        if at["method"] != "contract":
            u["non_contract"] += 1

    out: list[dict] = []
    violations: list[dict] = []
    for s in skills_meta:
        name = s["name"]
        layer = s.get("layer", "?")
        rt = str(s.get("runtime_safe", "false")).lower() == "true"
        if rt and layer != "A":
            violations.append({"skill": name,
                               "why": f"runtime-safe but Layer {layer} (expected A)"})
        if layer == "A" and not rt:
            violations.append({"skill": name, "why": "Layer A but not runtime-safe"})
        fw_violation = any(v["skill"] == name for v in violations)

        conf_row = conformance.get(name)
        if conf_row is not None:
            # conformance.md per-skill row is primary; a parse failure (or a
            # skill missing from the table) falls back to feedback.jsonl
            # classes only.
            classes = {k: conf_row[k] for k in ("friction", "gap", "diverged")
                       if conf_row[k]}
        else:
            classes = dict(drift_evidence.get(name) or {})
        status_text = (conf_row or {}).get("status", "")
        misused = "🔴" in status_text
        drift_active = misused or classes.get("diverged", 0) > 0
        open_note = status_text if re.search(
            r"\bopen\b|\bbacklog\b|not used as designed", status_text) else None
        drift = None
        if classes or misused:
            drift = {"active": drift_active, "classes": classes,
                     "latest": drift_latest.get(name) or None,
                     "open_note": open_note}

        healed = None
        if name in healed_by:
            h = healed_by[name]
            healed = {**h, "in_window": bool(h["accepted_at"])
                      and win_start <= h["accepted_at"] <= win_end}

        born = skill_born_date(name)
        new = None
        if born:
            new = {"born": born, "via": born_via.get(name, "git"),
                   "in_window": win_start <= born <= win_end}

        u = usage.get(name) or {"explicit": 0, "inferred": 0,
                                "last_used": "", "non_contract": 0}
        # 'ok' needs positive evidence beyond contract-subset authorization
        # (a skill_subset listing is permission, not observed use).
        tested = (confirmed.get(name, 0) > 0 or u["explicit"] > 0
                  or u["non_contract"] > 0)

        if fw_violation:
            state = "firewall_violation"
        elif drift_active:
            state = "drift"
        elif healed and healed["in_window"]:
            state = "healed"
        elif new and new["in_window"]:
            state = "new"
        elif name in BY_DESIGN:
            state = "by_design"
        elif not tested:
            state = "untested"
        else:
            state = "ok"

        out.append({
            "name": name,
            "layer": layer,
            "pack": s.get("pack", "?"),
            "runtime_safe": rt,
            "purpose": _trim(s.get("description", ""), 200),
            "governance": {
                "state": state,
                "conformance": conf_row,
                "drift": drift,
                "healed": healed,
                "new": new,
                "referenced_only_by_design": name in BY_DESIGN,
                "firewall_violation": fw_violation,
            },
            "usage": {"explicit": u["explicit"], "inferred": u["inferred"],
                      "last_used": u["last_used"] or None},
        })
    out.sort(key=lambda it: (it["layer"], it["name"]))
    return out, violations


# ---------------------------------------------------------------------------
# Inbox
# ---------------------------------------------------------------------------

def pending_gates(consumer: Path | None) -> list[dict]:
    """loop_memory pending rows minus iteration_ids present in loop_feedback."""
    if consumer is None:
        return []
    fb_ids = {r.get("iteration_id")
              for r in load_jsonl(consumer / "memory" / "loop_feedback.jsonl")}
    out = []
    for row in load_jsonl(consumer / "memory" / "loop_memory.jsonl"):
        iid = row.get("iteration_id")
        if row.get("gate_status") == "pending" and iid and iid not in fb_ids:
            out.append(row)
    return out


def build_inbox(
    consumer: Path | None,
    gates: list[dict],
    proposals: dict[str, dict],
    skills: list[dict],
    contracts: list[dict],
    now: datetime,
    today: str,
) -> list[dict]:
    items: list[dict] = []

    def _item(kind, id_, severity, reversible, since, title, detail,
              action_cmd, source, surface, skill=None, url=None):
        items.append({
            "id": id_, "kind": kind, "severity": severity,
            "reversible": reversible,
            "age_days": _days_between(since, today) if since else None,
            "since": since or None,
            "title": _trim(title, 100), "detail": _trim(detail, 240),
            "action_cmd": action_cmd, "source": source, "surface": surface,
            # Only framework items are signed off from the brain UI; apparatus
            # (research) items are shown view-only and resolved in their own UI.
            "actionable": surface == "framework",
            "link": {"skill": skill, "url": url},
        })

    cname = consumer.name if consumer is not None else "consumer"
    for g in gates:  # gate_verdict — append-only feedback row = an attestation
        iid = g.get("iteration_id", "")
        topic = ((g.get("seed") or {}).get("topic") or "").strip()
        _item("gate_verdict", iid, "med", False, g.get("ended_at") or None,
              f"{iid} awaiting gate verdict — {topic or 'untitled topic'}",
              f"iteration {iid} finished and awaits a human gate verdict "
              "(Step-8; no loop_feedback row yet)",
              GATE_CLI.format(iteration_id=iid),
              f"{cname}/memory/loop_memory.jsonl", "apparatus",
              skill="gate-check")

    for pid, p in sorted(proposals.items()):
        state = lifecycle_state(p)
        if state not in ("open", "human-review", "draft"):
            continue
        first = p["first"]
        # research-scoped proposals belong to the consumer apparatus, not this
        # framework — they are neither shown nor resolvable from the brain UI.
        if proposal_scope(first, cname) == "research":
            continue
        target = (first.get("target") or "").strip()
        is_skill = (first.get("target_type") or "").strip() == "skill"
        if state == "draft":
            # bubbled drift candidate — its own lane, distinct from review. NOT a
            # copy-command and NOT a Review→ link (it isn't in review yet); a human
            # (or the graduated auto-path) promotes it to 'open' first.
            _item("candidate_review", pid, "low", True,
                  first.get("timestamp") or None,
                  f"{pid} — {first.get('title', '')} (candidate)",
                  f"bubbled drift candidate ({first.get('agent_id', 'draft:auto')}); "
                  f"promote to 'open' to enter review, or discard "
                  f"(target {first.get('target_type', '?')}:{target})",
                  None,
                  "memory/brain/proposals.jsonl", "framework",
                  skill=target if is_skill else None,
                  url="memory/brain/proposals.jsonl")
            continue
        _item("proposal_review", pid, "med", True,
              first.get("timestamp") or None,
              f"{pid} — {first.get('title', '')} ({state})",
              f"latest verdict '{state}'; route via the review-proposal skill "
              f"(target {first.get('target_type', '?')}:{target})",
              f"review memory/brain/proposals.jsonl {pid}  "
              "# run the review-proposal skill",
              "memory/brain/proposals.jsonl", "framework",
              skill=target if is_skill else None,
              url="memory/brain/proposals.jsonl")

    if consumer is not None:  # bubble_unacked + finding_review (absent → none)
        mem = consumer / "memory"
        acked = {a.get("bubble_run_id")
                 for a in load_jsonl(mem / "coordinator_acks.jsonl")}
        for b in load_jsonl(mem / "coordinator_bubbles.jsonl"):
            rid = b.get("run_id") or b.get("timestamp") or "bubble"
            if b.get("run_id") and b["run_id"] in acked:
                continue
            _item("bubble_unacked", str(rid), "med", True,
                  b.get("timestamp") or None,
                  b.get("note") or "(bubble with no note)",
                  "the loop raised this to the human; no acknowledgement recorded",
                  "ack channel pending main-session blessing (plan A5)",
                  f"{cname}/memory/coordinator_bubbles.jsonl", "apparatus")
        overrides = {r.get("finding_id"): r.get("status")
                     for r in load_jsonl(mem / "surfaced_findings.status.jsonl")
                     if r.get("finding_id")}
        for fnd in load_jsonl(mem / "surfaced_findings.jsonl"):
            fid = fnd.get("finding_id")
            if not fid:
                continue
            status = overrides.get(fid, fnd.get("status"))
            if status not in ("surfaced", "in_review"):
                continue
            _item("finding_review", fid, "med", True,
                  fnd.get("promoted_at") or None,
                  fnd.get("title") or fid,
                  f"promoted finding awaits human interrogation (status: {status})",
                  ".venv-chroma/bin/python -m orchestrator.finding_session"
                  f"  # then: start {fid}",
                  f"{cname}/memory/surfaced_findings.jsonl", "apparatus")

        active = consumer / "run_state" / "active_run.json"
        if active.exists():  # stale_run — mtime-based per the v2 contract
            try:
                age_min = (now.timestamp() - active.stat().st_mtime) / 60.0
            except OSError:
                age_min = 0.0
            if age_min > STALE_RUN_AFTER_MIN:
                since = datetime.fromtimestamp(
                    active.stat().st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds").replace("+00:00", "Z")
                _item("stale_run", "active_run", "high", False, since,
                      "active_run.json stale — confirm no live process, then remove",
                      f"run_state/active_run.json mtime is {int(age_min)} min old "
                      "(>30 min) — possible lock-leak",
                      "inspect run_state/active_run.json; if no apparatus "
                      "process is live, remove the file (lock-leak cleanup)",
                      f"{cname}/run_state/active_run.json", "apparatus")

    for sk in skills:  # drift — one per skill in governance.state == drift
        if sk["governance"]["state"] != "drift":
            continue
        drift = sk["governance"]["drift"] or {}
        classes = drift.get("classes") or {}
        summary = " · ".join(f"{k}×{v}" for k, v in sorted(classes.items())) or "misuse"
        _item("drift", f"drift-{sk['name']}", "low", True,
              drift.get("latest"),
              f"{sk['name']} drift — {summary}",
              drift.get("open_note") or "conformance evidence diverges from the skill",
              "see memory/conformance.md",
              "memory/conformance.md", "framework",
              skill=sk["name"], url="memory/conformance.md")

    for c in contracts:  # contract_unverified — fail or completed-unchecked
        if c["done_check"] not in ("fail", "unverified"):
            continue
        sev = "high" if c["done_check"] == "fail" else "med"
        ledger = ("run_state/spawn.jsonl" if c["surface"] == "framework"
                  else f"{cname}/run_state/spawn.jsonl")
        _item("contract_unverified", c["spawn_id"], sev, True, c["date"],
              f"{c['spawn_id']} done-check {c['done_check']} — {c['task']}",
              f"spawn completed with done_condition_check={c['done_check']!r}; "
              "verify the done condition against the child's output",
              f"inspect {ledger} spawn_id={c['spawn_id']}",
              ledger, c["surface"], skill="spawn-contract", url=ledger)

    rank = {"high": 0, "med": 1, "low": 2}
    items.sort(key=lambda i: (rank[i["severity"]], i["since"] or "", i["id"]))
    return items


# ---------------------------------------------------------------------------
# Loop, timeline, incidents
# ---------------------------------------------------------------------------

def build_loop(proposals: dict[str, dict], rules: list[dict],
               feedback_rows: list[dict], skills: list[dict],
               today: str, consumer_name: str | None = None) -> dict:
    # The framework's proposal loop tracks only framework-scoped proposals;
    # research-scoped ones belong to the consumer apparatus (see proposal_scope).
    proposals = {pid: p for pid, p in proposals.items()
                 if proposal_scope(p["first"], consumer_name) == "framework"}
    newest_harvest = max((f.get("date", "") for f in feedback_rows), default="")
    newest_proposal = max((p["first"].get("timestamp", "")[:10]
                           for p in proposals.values()), default="")
    dormant = _days_between(newest_harvest, today) if newest_harvest else None
    prop_age = _days_between(newest_proposal, today) if newest_proposal else None
    if dormant is None or dormant > WINDOW_MAX_DAYS:
        state = ("half-dormant"
                 if prop_age is not None and prop_age <= WINDOW_MAX_DAYS
                 else "dormant")
    else:
        state = "active"

    verdicts = Counter(final_verdict(p) for p in proposals.values())
    # lane tally (draft|open|human-review|closed) — keeps drafts OUT of 'open'.
    lane = Counter(lifecycle_state(p) for p in proposals.values())
    newest_draft = max((p["first"].get("timestamp", "")[:10]
                        for p in proposals.values()
                        if lifecycle_state(p) == "draft"), default="")
    skills_created = sum(1 for s in skills
                         if (s["governance"]["new"] or {}).get("via", "git") != "git")
    skills_healed = sum(1 for s in skills if s["governance"]["healed"])

    chains = []
    for pid, p in proposals.items():
        first = p["first"]
        chains.append({
            "proposal_id": pid,
            "title": _trim(first.get("title", ""), 100),
            "target": (first.get("target") or "").strip(),
            "target_type": (first.get("target_type") or "").strip(),
            "origin_harvest": [ref.split(":", 1)[1]
                               for ref in (first.get("references") or [])
                               if isinstance(ref, str)
                               and ref.startswith("feedback.jsonl:")],
            "final_verdict": final_verdict(p),
            "lane": lifecycle_state(p),
            "rule_cited": p["latest"].get("rule_cited"),
            "filed_date": _date_of(first.get("timestamp")),
            "decided_at": (_date_of(p["latest"].get("timestamp"))
                           if p["latest"].get("verdict") else None),
            "lifecycle": [{"ts": r.get("timestamp", ""),
                           "verdict": r.get("verdict") or "open",
                           "actor": r.get("agent_id") or "unknown"}
                          for r in p["lifecycle"]],
        })
    chains.sort(key=lambda c: c["filed_date"], reverse=True)

    return {
        "stages": {
            "harvest": {"all": len(feedback_rows),
                        "newest": newest_harvest or None,
                        "dormant_days": dormant},
            "candidates": {"total": lane.get("draft", 0),
                           "newest": newest_draft or None},
            "proposals": {"open": lane.get("open", 0) + lane.get("human-review", 0),
                          "newest": newest_proposal or None},
            "review": {"accepted": verdicts.get("accepted", 0),
                       "auto_accept": verdicts.get("auto-accept", 0),
                       "auto_reject": verdicts.get("auto-reject", 0),
                       "human_review": verdicts.get("human-review", 0)},
            "enacted": {"rules": len(rules),
                        "skills_created": skills_created,
                        "skills_healed": skills_healed},
        },
        "state": state,
        "chains": chains,
    }


def load_narratives_split() -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for n in load_jsonl(NARRATIVES):
        if n.get("type") == "apparatus_event":
            continue
        buckets[n.get("_type_override") or "reflection"].append(n)
    return buckets


def build_timeline_and_incidents(
    proposals: dict[str, dict],
    fw_dec: list[dict],
    ap_dec: list[dict],
    narr: dict[str, list[dict]],
    feedback_rows: list[dict],
    contracts: list[dict],
    run_attr: list[dict],
    rules: list[dict],
    consumer: Path | None,
    win_start: str,
    win_end: str,
) -> tuple[list[dict], list[dict]]:
    timeline: list[dict] = []
    incidents: list[dict] = []

    def _row(date, ts, kind, id_, title, agent, verdict=None, is_flag=False,
             skill=None):
        timeline.append({"date": date, "ts": ts, "kind": kind, "id": id_,
                         "title": _trim(title, 100), "agent": agent,
                         "verdict": verdict, "is_flag": is_flag, "skill": skill})

    def _incident(id_, kind, date, severity, title, what, chain, source,
                  skill=None, rule=None):
        incidents.append({"id": id_, "kind": kind, "date": date,
                          "severity": severity, "title": _trim(title, 120),
                          "what_happened": _trim(what, 300), "chain": chain,
                          "source": source, "skill": skill, "rule": rule})

    rule_by_extends = {}
    extends_re = re.compile(r"extends\s+(?:the\s+)?\[\[([a-z0-9-]+)\]\]")
    for r in rules:
        m = extends_re.search(r.get("body", ""))
        if m:
            rule_by_extends[r["rule_id"]] = m.group(1)

    # proposals — filed + each verdict row
    for pid, p in proposals.items():
        title = p["first"].get("title", "") or pid
        target = (p["first"].get("target") or "").strip()
        skill = target if (p["first"].get("target_type") or "") == "skill" else None
        for r in p["lifecycle"]:
            ts = r.get("timestamp", "")
            verdict = r.get("verdict")
            _row(_date_of(ts), ts,
                 "proposal_reviewed" if verdict else "proposal_filed",
                 pid, title, r.get("agent_id") or "unknown",
                 verdict=verdict, skill=skill)
        latest = p["latest"]
        if final_verdict(p) in ("auto-reject", "rejected"):
            _incident(pid, "proposal_rejected", _date_of(latest.get("timestamp")),
                      "med", f"{pid} auto-rejected: {title}",
                      latest.get("verdict_reasoning") or "",
                      {"outcome": "proposed: " + title,
                       "expected": "proposal consistent with active rules",
                       "actual": _trim(latest.get("verdict_reasoning"), 300),
                       "correction_or_rule": latest.get("rule_cited")},
                      "memory/brain/proposals.jsonl",
                      skill=skill, rule=latest.get("rule_cited"))

    # decisions / corrections (framework + apparatus)
    rule_by_src = {(r.get("date"), r["title"].strip().lower()): r["rule_id"]
                   for r in rules}
    for d in fw_dec + ap_dec:
        if not d.get("date"):
            continue
        is_corr = d["type"] == "correction"
        agent = "claude-code-main" if d["side"] == "framework" else "human:decross1"
        _row(d["date"], d["date"] + "T00:00:00Z",
             "correction_written" if is_corr else "decision_logged",
             d["slug"], f"{d['head']} — {d['title']}", agent, is_flag=is_corr)
        if is_corr:
            rid = rule_by_src.get((d.get("date"), d["title"].strip().lower()))
            _incident(d["slug"], "correction", d["date"], "high", d["title"],
                      f"correction enacted into rule {rid}" if rid
                      else "correction logged",
                      {"outcome": "a wrong default was identified and corrected",
                       "expected": None, "actual": _trim(d.get("body"), 300),
                       "correction_or_rule": rid or "logged correction"},
                      "memory/DECISIONS.md" if d["side"] == "framework"
                      else "a_bgt_rsi/DECISIONS.md",
                      skill=rule_by_extends.get(rid), rule=rid)

    # narratives — corrections / anomalies / reflections
    for kind, nkind, sev, flag in (("correction", "correction_written", "high", True),
                                   ("anomaly", "anomaly_noted", "high", True),
                                   ("reflection", "reflection_written", None, False)):
        for n in narr.get(kind, []):
            ts = n.get("timestamp", "")
            nid = n.get("_slug") or slugify(n.get("task_id", "") or "untitled")
            title = n.get("_title") or n.get("task_id", "")
            _row(_date_of(ts), ts, nkind, nid, title,
                 n.get("agent_id") or "unknown", is_flag=flag)
            if flag:
                _incident(nid, kind, _date_of(ts), sev, title,
                          n.get("observed") or "",
                          {"outcome": _trim(n.get("did"), 400),
                           "expected": _trim(n.get("intent"), 400),
                           "actual": _trim(n.get("observed"), 400),
                           "correction_or_rule":
                               _trim(n.get("would_do_differently"), 400) or None},
                          "memory/brain/narratives.jsonl")

    # harvest sessions — one per (harvest_id, date)
    for hid, d in sorted({(f.get("harvest_id"), f.get("date"))
                          for f in feedback_rows if f.get("harvest_id")}):
        _row(d or "", (d or "") + "T00:00:00Z", "harvest_run", hid,
             f"{hid} harvest session", "claude-code-main", skill="harvest")

    # spawns — one per contract
    for c in contracts:
        _row(c["date"], c["date"] + "T00:00:00Z", "spawn_launched",
             c["spawn_id"], f"{c['spawn_id']} — {c['task']}", c["agent"],
             verdict=c["done_check"], skill="spawn-contract")

    # human gate verdicts (consumer loop_feedback)
    if consumer is not None:
        for r in load_jsonl(consumer / "memory" / "loop_feedback.jsonl"):
            ts = r.get("gated_at", "")
            who = f"human:{r.get('gated_by', 'unknown')}"
            _row(_date_of(ts), ts, "gate_verdict",
                 f"gate-{r.get('iteration_id', '')}",
                 f"{r.get('iteration_id', '')} gated {r.get('verdict', '?')} — "
                 f"{r.get('note', '')}", who, verdict=r.get("verdict"),
                 skill="gate-check")

    # run-log discipline flags (windowed with everything else below)
    for a in run_attr:
        flagged = (a["status"] in FLAG_STATUSES) or a["fallback_taken"]
        if not flagged:
            continue
        rid = f"runflag-{Path(a['file']).stem}-L{a['line']}"
        skill = "fallback" if a["fallback_taken"] and a["method"] != "skill_used" \
            else a["skill"]
        label = "fallback taken" if a["fallback_taken"] else a["status"]
        _row(a["date"], a["ts"], "run_flag", rid,
             f"{label}: {a['task'] or '(untitled step)'}", a["agent"],
             verdict=a["status"], is_flag=True, skill=skill)
        if win_start <= a["date"] <= win_end:
            _incident(rid, "run_flag", a["date"],
                      "high" if a["status"] in ("human_gate_blocked",
                                                "gate_armed") else "med",
                      f"{label}: {a['task']}", f"status={a['status']}",
                      {"outcome": a["task"], "expected": None, "actual": a["status"],
                       "correction_or_rule": None},
                      f"{a['file']} L{a['line']}", skill=skill)

    timeline = [t for t in timeline if win_start <= t["date"] <= win_end]
    timeline.sort(key=lambda t: (t["ts"], t["id"]), reverse=True)
    incidents.sort(key=lambda i: (i["date"], i["id"]), reverse=True)
    return timeline, incidents


# ---------------------------------------------------------------------------
# Top-level assembly
# ---------------------------------------------------------------------------

def build_rules(rules: list[dict], proposals: dict[str, dict]) -> list[dict]:
    enforced: Counter = Counter()
    for pid, p in proposals.items():
        if final_verdict(p) in ("auto-reject", "rejected") and p["latest"].get("rule_cited"):
            enforced[p["latest"]["rule_cited"]] += 1
    imp_re = re.compile(r"\*\*Imperative:\*\*\s*(.+?)(?:\n-\s\*\*|\Z)", re.DOTALL)
    ext_re = re.compile(r"extends\s+(?:the\s+)?\[\[([a-z0-9-]+)\]\]")
    out = []
    for r in rules:
        m = imp_re.search(r.get("body", ""))
        e = ext_re.search(r.get("body", ""))
        out.append({
            "id": r["rule_id"],
            "title": r["title"],
            "imperative": _trim(" ".join(m.group(1).split()) if m else "", 300),
            "enforced_count": enforced.get(r["rule_id"], 0),
            "extends_skill": e.group(1) if e else None,
            "date": r.get("date") or None,
        })
    return out


def build_days() -> list[dict]:
    out = []
    for p in sorted(VIEW_DIR.glob("????-??-??.md")):
        out.append({"date": p.stem, "file": p.name, "bytes": p.stat().st_size})
    return out


def build_summary(now: datetime | None = None) -> dict:
    # `now` is injectable so verify_brain_view.py can double-build against one
    # clock and deep-compare; the only intended delta is generated_at.
    if now is None:
        now = datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    today = generated_at[:10]
    consumer = resolve_consumer()

    skills_meta = load_skills()
    skill_names = {s["name"] for s in skills_meta}
    rules_raw = load_rules()
    proposals = collapse_proposals(load_jsonl(PROPOSALS))
    feedback_rows = [f for f in load_jsonl(FEEDBACK) if f.get("harvest_id")]
    fw_dec = load_decisions(FW_DECISIONS, "framework")
    ap_dec = (load_decisions(consumer / "DECISIONS.md", "apparatus")
              if consumer is not None else [])
    narr = load_narratives_split()
    week1_rows = (load_runlog(consumer / "run_state" / "week1.run.jsonl")
                  if consumer is not None else [])
    fw_rows = load_runlog(FW_RUN)
    run_attr = build_run_attributions(week1_rows, fw_rows)
    contracts = build_contracts(consumer, today)
    gates = pending_gates(consumer)
    loop_feedback = (load_jsonl(consumer / "memory" / "loop_feedback.jsonl")
                     if consumer is not None else [])

    # window anchor = newest observed event date across every source
    candidates = (
        [a["date"] for a in run_attr]
        + [_date_of(p["latest"].get("timestamp")) for p in proposals.values()]
        + [d.get("date", "") for d in fw_dec + ap_dec]
        + [_date_of(n.get("timestamp")) for ns in narr.values() for n in ns]
        + [f.get("date", "") for f in feedback_rows]
        + [c["date"] for c in contracts]
        + [_date_of(r.get("gated_at")) for r in loop_feedback]
    )
    win_end = max((d for d in candidates if d), default=today)
    win_start = (date_cls.fromisoformat(win_end)
                 - timedelta(days=WINDOW_MAX_DAYS - 1)).isoformat()

    # human actions feed the human agent's presence
    human_actions: list[tuple[str, str]] = []
    for p in proposals.values():
        for r in p["lifecycle"]:
            aid = (r.get("agent_id") or "").strip()
            if aid.startswith("human:"):
                human_actions.append((r.get("timestamp", ""), aid))
    for r in loop_feedback:
        human_actions.append((r.get("gated_at", ""),
                              f"human:{r.get('gated_by', 'unknown')}"))

    agents, matrix, attributions = build_agents_and_matrix(
        run_attr, feedback_rows, contracts, human_actions, skill_names,
        win_start, win_end)
    skills, violations = build_skills(
        skills_meta, feedback_rows, parse_conformance(), proposals, rules_raw,
        attributions, win_start, win_end)
    inbox = build_inbox(consumer, gates, proposals, skills, contracts, now, today)
    loop = build_loop(proposals, rules_raw, feedback_rows, skills, today,
                      consumer.name if consumer is not None else None)
    timeline, incidents = build_timeline_and_incidents(
        proposals, fw_dec, ap_dec, narr, feedback_rows, contracts, run_attr,
        rules_raw, consumer, win_start, win_end)
    rules = build_rules(rules_raw, proposals)

    # status strip ---------------------------------------------------------
    sev = Counter(i["severity"] for i in inbox)
    drift_skills = [s for s in skills if s["governance"]["state"] == "drift"]
    worst = max(drift_skills,
                key=lambda s: sum((s["governance"]["drift"] or {})
                                  .get("classes", {}).values()),
                default=None)
    # recall floor = the newest correction (its id names the floor; its date
    # drives the age) — same math as v1's newest_correction_date/_id pair.
    corr_refs = ([( _date_of(n.get("timestamp")),
                    n.get("_slug") or slugify(n.get("task_id", "") or "untitled"))
                  for n in narr.get("correction", [])]
                 + [(d["date"], d["slug"]) for d in fw_dec + ap_dec
                    if d["type"] == "correction" and d.get("date")])
    newest_corr = max(corr_refs, default=None)
    needs_total = len(inbox)
    if violations:
        system = "critical"
    elif needs_total or drift_skills or loop["state"] != "active":
        system = "attention"
    else:
        system = "ok"

    agent_rows = sum(1 for a in run_attr if a["explicit_agent"])
    skill_used_rows = sum(1 for a in run_attr if a["method"] == "skill_used")
    total_rows = len(run_attr)

    # data span, not the trailing window — the page's stepper needs to know
    # how far back the observed record actually reaches
    oldest_event = min((d for d in candidates if d), default=win_end)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "repo": str(REPO),
        "consumer": str(consumer) if consumer is not None else None,
        "window": {
            "default_days": WINDOW_DEFAULT_DAYS,
            "min_days": WINDOW_MIN_DAYS,
            "max_days": WINDOW_MAX_DAYS,
            "oldest_event": oldest_event,
            "newest_event": win_end,
        },
        "status_strip": {
            "system": system,
            "needs_you": {"total": needs_total, "high": sev.get("high", 0),
                          "med": sev.get("med", 0), "low": sev.get("low", 0)},
            "drift": {"skills": len(drift_skills),
                      "worst": worst["name"] if worst else None},
            "candidates": {"total": loop["stages"]["candidates"]["total"]},
            "loop": {"state": loop["state"],
                     "dormant_days": loop["stages"]["harvest"]["dormant_days"]},
            "firewall": {"status": "intact" if not violations else "breached",
                         "violations": len(violations)},
            "freshness": {"newest_event": win_end,
                          "recall_floor_age_days":
                              _days_between(newest_corr[0], today)
                              if newest_corr else None,
                          "recall_floor": newest_corr[1] if newest_corr else None},
        },
        "inbox": inbox,
        "agents": agents,
        "skills": skills,
        "matrix": matrix,
        "contracts": contracts,
        "loop": loop,
        "timeline": timeline,
        "incidents": incidents,
        "rules": rules,
        "attribution": {
            "agent_rows": agent_rows,
            "total_rows": total_rows,
            "skill_used_rows": skill_used_rows,
            "note": (f"raw run-log rows carry agent on {agent_rows}/{total_rows} "
                     f"and skill_used on {skill_used_rows}/{total_rows}; the "
                     "attribution ladder infers the rest and labels every "
                     "inference (P-008 open: make agent required in the "
                     "consumer run-log)."),
        },
        "days": build_days(),
    }


# ---------------------------------------------------------------------------
# Emit (compare-before-write, generated_at excluded)
# ---------------------------------------------------------------------------

def _normalized(obj: dict) -> dict:
    d = dict(obj)
    d["generated_at"] = None
    return d


def parse_summary_js(text: str) -> dict | None:
    """Extract the object literal from `window.BRAIN_SUMMARY = {...};`."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def emit(summary: dict, out_dir: Path) -> bool:
    """Write summary.json + summary_data.js. Returns True when files changed.
    No-op (both files untouched) when content matches modulo generated_at."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "summary.json"
    js_path = out_dir / "summary_data.js"

    unchanged = False
    if json_path.exists() and js_path.exists():
        try:
            old_json = json.loads(json_path.read_text())
            old_js = parse_summary_js(js_path.read_text())
            unchanged = (old_js is not None
                         and _normalized(old_json) == _normalized(summary)
                         and _normalized(old_js) == _normalized(summary))
        except (OSError, json.JSONDecodeError, AttributeError):
            unchanged = False
    if unchanged:
        return False

    payload = json.dumps(summary, indent=2, ensure_ascii=False)
    # Atomic write (tmp + os.replace): brain_server schedules this regen on a
    # daemon thread that can run WHILE the HTTP server is serving these files, so
    # a plain truncate-then-write could be read torn. os.replace is atomic on the
    # same filesystem.
    _atomic_write(json_path, payload + "\n")
    _atomic_write(js_path, "window.BRAIN_SUMMARY = " + payload + ";\n")
    return True


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project the brain to schema-v2 summary.json + summary_data.js.")
    parser.add_argument("--out-dir", type=Path, default=VIEW_DIR,
                        help="Output directory (default: memory/brain/view).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the rollup; write nothing.")
    args = parser.parse_args()

    summary = build_summary()
    s = summary["status_strip"]
    print("summary v2 — governance/skills/memory projection")
    print(f"  generated_at: {summary['generated_at']}  consumer: {summary['consumer']}")
    print(f"  window: {summary['window']['oldest_event']} → "
          f"{summary['window']['newest_event']} (max {WINDOW_MAX_DAYS}d)")
    print(f"  status: system={s['system']}  needs_you={s['needs_you']['total']} "
          f"(h{s['needs_you']['high']}/m{s['needs_you']['med']}/l{s['needs_you']['low']})  "
          f"drift={s['drift']['skills']} (worst {s['drift']['worst']})  "
          f"loop={s['loop']['state']}/{s['loop']['dormant_days']}d  "
          f"firewall={s['firewall']['status']}  "
          f"recall_floor={s['freshness']['recall_floor']} "
          f"({s['freshness']['recall_floor_age_days']}d)")
    print(f"  agents={len(summary['agents'])}  skills={len(summary['skills'])}  "
          f"matrix_cells={len(summary['matrix']['cells'])}  "
          f"contracts={len(summary['contracts'])}")
    print(f"  timeline={len(summary['timeline'])} rows (windowed)  "
          f"incidents={len(summary['incidents'])}  rules={len(summary['rules'])}  "
          f"days={len(summary['days'])}")
    a = summary["attribution"]
    print(f"  attribution: agent {a['agent_rows']}/{a['total_rows']}  "
          f"skill_used {a['skill_used_rows']}/{a['total_rows']}")

    if args.dry_run:
        print("DRY RUN — nothing written.")
        return 0
    changed = emit(summary, args.out_dir)
    state = "wrote" if changed else "unchanged"
    print(f"  {state} {args.out_dir / 'summary.json'} + summary_data.js")
    return 0


if __name__ == "__main__":
    sys.exit(main())
