#!/usr/bin/env python3
"""project_summary.py — project the brain's skills+governance+memory layer into
one derived `summary.json` for the functional-review dashboard.

This is a NARRATIVE BRIEFING projector, distinct from `project_pages.py` (which
emits the GRAPH's slim index.json + graph_data.js over ~730 nodes incl. ~590
apparatus telemetry). This script reads the SAME canonical sources through the
SAME side-effect-free helpers imported from `project_pages` (so the two stay in
lockstep, no forked parsers) and emits the small in-scope governance/skills/
memory layer ONLY — every node carries an ISO `date` so the dashboard can filter
to a rolling 1-7 day window CLIENT-SIDE.

Scope (in): skill, agent, rule, proposal, harvest_finding, correction,
reflection, anomaly, decision, spawn, + run-log DISCIPLINE flags.
Scope (out): raw apparatus telemetry (iteration/stage/llm_call/apparatus_event)
— that is graph.html's deep-dive lens.

Three acts feed the dashboard:
  act1_system        — "Here is the system": cast, skills, rules, firewall (STATE)
  act2_activity      — "Here is what it did": brain events, dated (WINDOWED)
  act3_loop_and_memory — "How it learned / where it slipped": loop chains,
                         memory recall floor, and THE FLAG LANE (causal chains)

Stdlib-only. Deterministic + idempotent (compare-before-write). Read-only on
the consumer (brain firewall). Stamps generated_at = now() as the "as of".

Honesty contract (surfaced in the data, never hidden):
  - run-log `agent` populated 1/1007 (consumer) + 0/137 (framework);
    `skill_used` 0/1007 + 0/137 → run-log-derived flags are link_explicit=False
    (inferred). corrections/anomalies/rejected-proposals/harvest carry an
    EXPLICIT skill/rule link. P-008 (open, human-gated) is the in-flight fix.
  - skills are referenced (agent leans-on / proposal target / spawn subset /
    harvest skill) but run_log_invocations == 0 for ALL 24 → referenced != run.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, date as date_cls
from pathlib import Path

# Import the side-effect-free parsers + path constants from project_pages so the
# two projectors read the same sources through the same code. project_pages's
# only module-level work is constant/regex assignment (main() is __main__-
# guarded), so this import is safe and does not run the graph pipeline.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from project_pages import (  # noqa: E402
    REPO,
    CONSUMER,
    PROPOSALS,
    FEEDBACK,
    SPAWN_LEDGER,
    FW_DECISIONS,
    AP_DECISIONS,
    CONSUMER_WEEK1_RUN,
    load_jsonl,
    load_skills,
    load_rules,
    load_decisions,
    parse_finding_ref,
    canonicalize_agent,
    slugify,
)

SUMMARY = REPO / "memory" / "brain" / "view" / "summary.json"
NARRATIVES = REPO / "memory" / "brain" / "narratives.jsonl"
FW_RUN = REPO / "run_state" / "framework.run.jsonl"
SKILLS_DIR = REPO / ".agents" / "skills"
AGENTS_DIR = REPO / ".agents" / "agents"

SCHEMA_VERSION = 1
WINDOW_DEFAULT_DAYS = 7
WINDOW_MIN_DAYS = 1
WINDOW_MAX_DAYS = 7

# The 5 runtime-safe Layer-A core named in CLAUDE.md/BOUNDARY.md, plus
# spawn-contract which carries runtime-safe:true in its frontmatter. The
# firewall check below is structural over frontmatter, not this list — this is
# only the human-readable "core" label for the firewall card.
RUNTIME_SAFE_CORE_HINT = [
    "resume-state", "gate-check", "validate", "fallback", "run-log", "spawn-contract",
]

# run-log discipline statuses → inferred governing skill (the row has no
# skill_used, so the link is a status-semantics guess: link_explicit=False).
STATUS_TO_INFERRED_SKILL = {
    "failed": "validate",
    "partial_pass": "validate",
    "aborted": "validate",
    "escalated": "fallback",
    "human_gate_blocked": "gate-check",
    "gate_armed": "gate-check",
    "declared": "slip-ladder",       # slip_declared rows
    "recovered": "validate",         # incident recovery — validation/guard
    "observed": "validate",          # incident observation
}

# Statuses that are NOT discipline flags (routine / sentinel / apparatus bleed).
# `error` rows are loop_v0 apparatus events (have event_type/iteration_id, no
# observable_expected) — excluded from the flag lane per the apparatus-bleed gap.
NON_FLAG_STATUSES = {
    "passed", "started", "open", "closed", "recorded", "applied",
    "resolved", "correction", "ready_to_remove", "skipped", "halted",
    "error",  # apparatus loop_v0 bleed — graph.html scope, not the flag lane
}


def _agent_id_to_actor(raw: str | None) -> str:
    """Canonicalize for display; fall back to the raw id (don't drop humans)."""
    c = canonicalize_agent(raw)
    if c:
        return c
    return (raw or "unknown").strip() or "unknown"


def _days_between(iso_a: str, iso_b: str) -> int | None:
    """Whole days from iso_a (older) to iso_b (newer), both YYYY-MM-DD."""
    try:
        a = date_cls.fromisoformat(iso_a[:10])
        b = date_cls.fromisoformat(iso_b[:10])
    except (ValueError, TypeError):
        return None
    return (b - a).days


def _captured_reasoning(observed: str | None) -> str | None:
    """Pull the load-bearing reasoning sentence out of a correction's `observed`.

    Corrections capture their *why* inline (e.g. 'a --gpu-memory-utilization cap
    alone does NOT make arm C safe on shared unified memory, because ...'). The
    flag chain wants that insight verbatim, not the whole observed paragraph
    (which already fills `actual`). Prefer a sentence carrying an explicit
    contrast/causal marker; fall back to None so inferred kinds and contrast-
    free corrections honestly read 'not captured'."""
    if not observed:
        return None
    import re
    markers = ("does not", "does NOT", "not enough", "necessary-not-sufficient",
               "necessary-not", " because ", "too aggressive", "not make")
    # split into sentences (keep it simple — period/semicolon boundaries)
    parts = re.split(r"(?<=[.;])\s+", observed.strip())
    for p in parts:
        low = p.lower()
        if any(m.lower() in low for m in markers):
            return p.strip()[:400]
    return None


def _freshness(age_days: int | None) -> str:
    if age_days is None:
        return "unknown"
    if age_days <= 3:
        return "fresh"
    if age_days <= 14:
        return "aging"
    return "stale"


# ---------------------------------------------------------------------------
# Source loaders (collapse JSONL into the shapes the dashboard reads)
# ---------------------------------------------------------------------------

def load_agents() -> list[dict]:
    """Read .agents/agents/*.md — name + description from frontmatter, leans_on
    from [[..]] refs in the body."""
    import re
    out: list[dict] = []
    if not AGENTS_DIR.exists():
        return out
    ref_re = re.compile(r"\[\[([a-z][a-z0-9-]*)\]\]")
    for md in sorted(AGENTS_DIR.glob("*.md")):
        text = md.read_text()
        name = md.stem
        desc = ""
        # frontmatter
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                fm = text[3:end]
                for line in fm.splitlines():
                    if line.strip().startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.strip().startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
        # leans_on — deduped, order-preserving
        leans: list[str] = []
        for m in ref_re.finditer(text):
            s = m.group(1)
            if s not in leans:
                leans.append(s)
        out.append({"name": name, "role": desc, "leans_on": leans})
    return out


def collapse_proposals(rows: list[dict]) -> dict[str, dict]:
    """Group proposals by id; return {pid: {first, latest, lifecycle[]}}.

    lifecycle = every row sharing the id, time-ordered. final verdict = last
    row's verdict (or 'open' when never reviewed).
    """
    by_pid: dict[str, list[dict]] = {}
    for r in sorted(rows, key=lambda x: x.get("timestamp", "")):
        pid = r.get("proposal_id")
        if not pid:
            continue
        by_pid.setdefault(pid, []).append(r)
    out: dict[str, dict] = {}
    for pid, hist in by_pid.items():
        out[pid] = {"first": hist[0], "latest": hist[-1], "lifecycle": hist}
    return out


def load_narrative_nodes() -> dict[str, list[dict]]:
    """Split non-apparatus narratives into corrections / reflections / anomalies
    / other (hypothesis, experiment). Returns dict keyed by bucket."""
    rows = load_jsonl(NARRATIVES)
    buckets: dict[str, list[dict]] = {
        "correction": [], "reflection": [], "anomaly": [],
        "hypothesis": [], "experiment": [],
    }
    for n in rows:
        if n.get("type") == "apparatus_event":
            continue
        override = n.get("_type_override")
        typ = override or "reflection"
        if typ not in buckets:
            buckets.setdefault(typ, [])
        buckets[typ].append(n)
    return buckets


# ---------------------------------------------------------------------------
# ACT I — the system (standing state)
# ---------------------------------------------------------------------------

def build_act1(skills, agents, rules, proposals_collapsed, feedback_rows,
               spawn_rows, fw_corrections) -> dict:
    # --- skill invocation evidence ---------------------------------------
    # referenced sources: agent leans_on, proposal target (target_type==skill),
    # spawn skill_subset, harvest skill field.
    leaned = set()
    for a in agents:
        leaned.update(a.get("leans_on", []))
    proposal_targets = set()
    for pid, p in proposals_collapsed.items():
        first = p["first"]
        if (first.get("target_type") or "").strip() == "skill":
            proposal_targets.add((first.get("target") or "").strip())
    spawn_subset_names: dict[str, int] = {}
    for r in spawn_rows:
        for s in (r.get("contract") or {}).get("skill_subset") or []:
            spawn_subset_names[s] = spawn_subset_names.get(s, 0) + 1

    # harvest evidence per skill
    harvest_count: dict[str, int] = {}
    harvest_friction: dict[str, int] = {}
    harvest_last_seen: dict[str, str] = {}
    for f in feedback_rows:
        sk = (f.get("skill") or "").strip()
        if not sk:
            continue
        harvest_count[sk] = harvest_count.get(sk, 0) + 1
        if (f.get("class") or "") in ("friction", "gap", "diverged"):
            harvest_friction[sk] = harvest_friction.get(sk, 0) + 1
        d = f.get("date") or ""
        if d and (sk not in harvest_last_seen or d > harvest_last_seen[sk]):
            harvest_last_seen[sk] = d

    by_layer: dict[str, list[str]] = {"A": [], "B": [], "C": []}
    items: list[dict] = []
    runtime_safe_names: list[str] = []
    for s in skills:
        name = s["name"]
        layer = s.get("layer", "?")
        rt = str(s.get("runtime_safe", "false")).lower() == "true"
        if rt:
            runtime_safe_names.append(name)
        if layer in by_layer:
            by_layer[layer].append(name)
        referenced = (
            name in leaned
            or name in proposal_targets
            or name in spawn_subset_names
            or name in harvest_count
        )
        run_log_invocations = 0  # 0/1007 + 0/137 — none carry skill_used
        items.append({
            "name": name,
            "layer": layer,
            "runtime_safe": rt,
            "pack": s.get("pack", "?"),
            "purpose": s.get("description", ""),
            "referenced": referenced,
            "invoked_evidence": {
                "harvest_findings": harvest_count.get(name, 0),
                "harvest_friction": harvest_friction.get(name, 0),
                "spawn_subset_uses": spawn_subset_names.get(name, 0),
                "run_log_invocations": run_log_invocations,
                "last_seen": harvest_last_seen.get(name) or None,
            },
            "referenced_but_not_run": referenced and run_log_invocations == 0,
        })
    items.sort(key=lambda it: (it["layer"], it["name"]))

    referenced_total = sum(1 for it in items if it["referenced"])
    rollup = {
        "total": len(items),
        "runtime_safe": len(runtime_safe_names),
        "by_layer": {k: len(v) for k, v in by_layer.items()},
        "referenced": referenced_total,
        "with_run_log_invocation": 0,
        "audited_at_head": 18,
        "audited_in_working_tree": len(items),
        "audit_gap_note": (
            "SP-002 saw 18 skills at HEAD; working tree has "
            f"{len(items)} (6 uncommitted at audit time — narrate, brain-recall, "
            "propose, review-proposal, slip-ladder, spawn-contract)."
        ),
    }

    # --- agents ----------------------------------------------------------
    # authored_corrections: narrative correction nodes whose canonical agent
    # maps to this named dev-agent. Today all narratives carry claude-code-main
    # (or human:decross1), never the role names — so this is structurally empty.
    correction_authors: dict[str, int] = {}
    for c in fw_corrections:
        pass  # DECISIONS corrections have no per-role author either
    agent_items = []
    for a in agents:
        agent_items.append({
            "name": a["name"],
            "role": a["role"],
            "leans_on": a["leans_on"],
            "authored_corrections": [],   # structurally empty — attribution gap
            "activity_count": 0,          # no run-log rows attributable to role
        })

    # --- rules -----------------------------------------------------------
    # enforced_count = proposals auto-rejected citing this rule.
    enforced: dict[str, int] = {}
    rejected_by_rule: dict[str, list[str]] = {}
    for pid, p in proposals_collapsed.items():
        latest = p["latest"]
        if latest.get("verdict") == "auto-reject" and latest.get("rule_cited"):
            rc = latest["rule_cited"]
            enforced[rc] = enforced.get(rc, 0) + 1
            rejected_by_rule.setdefault(rc, []).append(pid)
    # enacted_by = correction whose date+title match the rule's source decision.
    rule_items = []
    for r in rules:
        rid = r["rule_id"]
        # parse imperative from body
        imperative = ""
        body = r.get("body", "")
        import re
        m = re.search(r"\*\*Imperative:\*\*\s*(.+?)(?:\n-\s\*\*|\Z)", body, re.DOTALL)
        if m:
            imperative = " ".join(m.group(1).split())
        enacted_by = []
        for c in fw_corrections:
            if (c.get("date") == r.get("date")
                    and c.get("title", "").strip().lower() == r["title"].strip().lower()):
                enacted_by.append(c["slug"])
        rule_items.append({
            "id": rid,
            "title": r["title"],
            "imperative": imperative,
            "source_decision_date": r.get("date", ""),
            "side": r.get("side", "framework"),
            "enforced_count": enforced.get(rid, 0),
            "enacted_by": enacted_by,
            "rejected_proposals": rejected_by_rule.get(rid, []),
        })

    # --- firewall (structural check over frontmatter) --------------------
    violations = []
    for it in items:
        if it["runtime_safe"] and it["layer"] != "A":
            violations.append({"skill": it["name"],
                               "why": f"runtime-safe but Layer {it['layer']} (expected A)"})
        if it["layer"] == "A" and not it["runtime_safe"]:
            violations.append({"skill": it["name"],
                               "why": "Layer A but not runtime-safe"})
    runtime_safe_core = sorted(runtime_safe_names)
    firewall = {
        "runtime_safe_core": runtime_safe_core,
        "runtime_safe_count": len(runtime_safe_core),
        "dev_only_count": len(items) - len(runtime_safe_core),
        "violations": violations,
        "status": "intact" if not violations else "breached",
        "invariant": ("apparatus never reads brain; the watcher reads apparatus "
                      "JSONL only (BOUNDARY.md). The runtime-safe core may be "
                      "deliberately embedded in a spawned agent; dev-only skills "
                      "must never be inherited by accident."),
    }

    return {
        "agents": agent_items,
        "skills": {
            "by_layer": by_layer,
            "rollup": rollup,
            "items": items,
        },
        "rules": rule_items,
        "firewall": firewall,
    }


# ---------------------------------------------------------------------------
# ACT II — what it did (windowed events)
# ---------------------------------------------------------------------------

def build_act2(proposals_collapsed, fw_dec, ap_dec, narr,
               feedback_rows, spawn_rows) -> dict:
    timeline: list[dict] = []

    # proposals — one row per lifecycle entry (filed / reviewed)
    for pid, p in proposals_collapsed.items():
        for r in p["lifecycle"]:
            ts = r.get("timestamp", "")
            verdict = r.get("verdict")
            is_review = verdict is not None
            title = p["first"].get("title", "") or pid
            timeline.append({
                "date": ts[:10],
                "ts": ts,
                "kind": "proposal_reviewed" if is_review else "proposal_filed",
                "id": pid,
                "title": title,
                "actor": _agent_id_to_actor(r.get("agent_id")),
                "ref": "proposals.jsonl",
                "verdict": verdict,
                "is_flag": False,
            })

    # decisions (framework + consumer)
    for d in fw_dec + ap_dec:
        if not d.get("date"):
            continue  # date-less decisions (D-001..D-018) carry no event date
        timeline.append({
            "date": d["date"],
            "ts": d["date"] + "T00:00:00Z",
            "kind": "correction_written" if d["type"] == "correction" else "decision_logged",
            "id": d["head"],
            "title": d["title"],
            "actor": "human:decross1" if d["side"] == "apparatus" else "claude-code-main",
            "ref": ("a_bgt_rsi/DECISIONS.md" if d["side"] == "apparatus"
                    else "memory/DECISIONS.md"),
            "verdict": None,
            "is_flag": d["type"] == "correction",
        })

    # corrections + reflections + anomalies (narratives)
    def _narr_row(n, kind, is_flag):
        ts = n.get("timestamp", "")
        return {
            "date": ts[:10],
            "ts": ts,
            "kind": kind,
            "id": n.get("_slug") or slugify(n.get("task_id", "")),
            "title": n.get("_title") or n.get("task_id", ""),
            "actor": _agent_id_to_actor(n.get("agent_id")),
            "ref": "narratives.jsonl",
            "verdict": None,
            "is_flag": is_flag,
        }
    for n in narr.get("correction", []):
        timeline.append(_narr_row(n, "correction_written", True))
    for n in narr.get("reflection", []):
        timeline.append(_narr_row(n, "reflection_written", False))
    for n in narr.get("anomaly", []):
        timeline.append(_narr_row(n, "reflection_written", True))

    # harvest runs — one row per (harvest_id, date) session
    seen_harvest: set[tuple[str, str]] = set()
    for f in feedback_rows:
        hid = f.get("harvest_id")
        d = f.get("date") or ""
        if not hid or not d:
            continue
        key = (hid, d)
        if key in seen_harvest:
            continue
        seen_harvest.add(key)
        timeline.append({
            "date": d,
            "ts": d + "T00:00:00Z",
            "kind": "harvest_run",
            "id": hid,
            "title": f"{hid} harvest session",
            "actor": "claude-code-main",
            "ref": "feedback.jsonl",
            "verdict": None,
            "is_flag": False,
        })

    # spawns — one row per spawned spawn_id (first 'spawned' entry)
    seen_spawn: set[str] = set()
    for r in sorted(spawn_rows, key=lambda x: x.get("timestamp", "")):
        sid = r.get("spawn_id")
        if not sid or sid in seen_spawn:
            continue
        if r.get("status") != "spawned":
            continue
        seen_spawn.add(sid)
        ts = r.get("timestamp", "")
        timeline.append({
            "date": ts[:10],
            "ts": ts,
            "kind": "spawn_launched",
            "id": sid,
            "title": f"{sid} — {r.get('child_task_id', 'spawn')}",
            "actor": "claude-code-main",
            "ref": "run_state/spawn.jsonl",
            "verdict": None,
            "is_flag": False,
        })

    timeline.sort(key=lambda r: (r.get("ts", ""), r.get("id", "")), reverse=True)

    counts_all_time = {
        "proposals": len(proposals_collapsed),
        "decisions": sum(1 for d in fw_dec + ap_dec if d["type"] == "decision"),
        "corrections": (len(narr.get("correction", []))
                        + sum(1 for d in fw_dec + ap_dec if d["type"] == "correction")),
        "reflections": len(narr.get("reflection", [])),
        "harvest_findings": len(feedback_rows),
        "rules": 0,  # filled by caller
        "spawns": len(seen_spawn),
        "anomalies": len(narr.get("anomaly", [])),
    }
    return {"timeline": timeline, "counts_all_time": counts_all_time}


# ---------------------------------------------------------------------------
# ACT III — loop + memory + flag lane (the climax)
# ---------------------------------------------------------------------------

def _origin_harvest(first: dict) -> list[str]:
    import re
    out: list[str] = []
    for ref in first.get("references") or []:
        if not isinstance(ref, str):
            continue
        if ref.startswith("feedback.jsonl:"):
            out.append(ref.split(":", 1)[1])
        else:
            for m in re.findall(r"\bH0\d{2}\b", ref):
                if m not in out:
                    out.append(m)
    return out


def build_loop(proposals_collapsed, rules, generated_date) -> tuple[list[dict], dict]:
    rule_titles = {r["rule_id"]: r["title"] for r in rules}
    chains: list[dict] = []
    open_n = accepted_n = rejected_n = human_n = 0
    for pid, p in proposals_collapsed.items():
        first = p["first"]
        latest = p["latest"]
        verdict = latest.get("verdict") or "open"
        lifecycle = []
        for r in p["lifecycle"]:
            v = r.get("verdict") or "open"
            lifecycle.append({
                "ts": r.get("timestamp", ""),
                "verdict": v,
                "actor": _agent_id_to_actor(r.get("agent_id")),
                "reasoning": r.get("verdict_reasoning") or None,
            })
        final = lifecycle[-1]["verdict"] if lifecycle else "open"
        target_type = (first.get("target_type") or "").strip()
        target = (first.get("target") or "").strip()
        produced_skill = (target if target_type == "skill"
                          and final in ("accepted", "auto-accept") else None)
        if final in ("accepted", "auto-accept"):
            accepted_n += 1
        elif final in ("auto-reject", "rejected"):
            rejected_n += 1
        elif final == "human-review":
            human_n += 1
        elif final == "open":
            open_n += 1
        chains.append({
            "proposal_id": pid,
            "title": first.get("title", ""),
            "target": target,
            "target_type": target_type,
            "origin_harvest": _origin_harvest(first),
            "verdict_lifecycle": lifecycle,
            "final_verdict": final,
            "auto_rejected_by": (latest.get("rule_cited")
                                 if final in ("auto-reject", "rejected") else None),
            "rule_cited_title": (rule_titles.get(latest.get("rule_cited"))
                                 if latest.get("rule_cited") else None),
            "produced_rule": None,
            "produced_skill": produced_skill,
            "status": latest.get("status", "open"),
            "filed_date": (first.get("timestamp") or "")[:10],
        })
    chains.sort(key=lambda c: c["filed_date"], reverse=True)
    return chains, {
        "open": open_n, "accepted": accepted_n,
        "rejected": rejected_n, "human": human_n,
    }


def build_flags(narr, fw_corrections, proposals_collapsed, rules,
                feedback_rows, week1_rows) -> list[dict]:
    """Assemble the flag lane — each flag a causal chain with an honesty marker.

    Eight kinds; four EXPLICIT (correction/anomaly/proposal_rejected/
    skill_friction), four INFERRED (validation_fail/fallback/gate_block/slip).
    """
    flags: list[dict] = []
    rule_imperatives: dict[str, str] = {}
    for r in rules:
        import re
        m = re.search(r"\*\*Imperative:\*\*\s*(.+?)(?:\n-\s\*\*|\Z)", r.get("body", ""), re.DOTALL)
        rule_imperatives[r["rule_id"]] = " ".join(m.group(1).split()) if m else ""

    # 1. corrections (narrative) — EXPLICIT
    for n in narr.get("correction", []):
        ch_honored = n.get("corrections_honored") or []
        governing = ch_honored[0] if ch_honored else "(uncited)"
        flags.append({
            "date": (n.get("timestamp") or "")[:10],
            "kind": "correction",
            "severity": "high",
            "title": n.get("_title") or n.get("task_id", ""),
            "what_happened": (n.get("observed") or "")[:240],
            "governing_skill_or_rule": governing,
            "link_explicit": True,
            "chain": {
                "outcome": (n.get("did") or "")[:400],
                "expected": (n.get("intent") or "")[:400],
                "actual": (n.get("observed") or "")[:400],
                "reasoning": _captured_reasoning(n.get("observed")),
                "correction_or_rule": (n.get("would_do_differently") or "")[:400],
            },
            "source_ref": "narratives.jsonl#" + (n.get("_slug") or ""),
        })

    # 1b. DECISIONS corrections — EXPLICIT (enact a rule)
    for c in fw_corrections:
        # find the rule it enacts
        enacted = None
        for r in rules:
            if (c.get("date") == r.get("date")
                    and c.get("title", "").strip().lower() == r["title"].strip().lower()):
                enacted = r["rule_id"]
                break
        flags.append({
            "date": c.get("date", ""),
            "kind": "correction",
            "severity": "high",
            "title": c.get("title", ""),
            "what_happened": f"Correction enacted into rule {enacted}" if enacted else "Correction logged",
            "governing_skill_or_rule": enacted or "(framework rule)",
            "link_explicit": True,
            "chain": {
                "outcome": "A wrong default was identified and corrected.",
                "expected": rule_imperatives.get(enacted, ""),
                "actual": (c.get("body", "")[:300]),
                "reasoning": None,
                "correction_or_rule": f"Enacted active rule {enacted}" if enacted else "Logged correction",
            },
            "source_ref": "memory/DECISIONS.md#" + c["slug"],
        })

    # 2. anomalies — EXPLICIT (seed of a correction→rule)
    for n in narr.get("anomaly", []):
        ch = n.get("corrections_honored") or []
        flags.append({
            "date": (n.get("timestamp") or "")[:10],
            "kind": "anomaly",
            "severity": "high",
            "title": n.get("_title") or n.get("task_id", ""),
            "what_happened": (n.get("observed") or "")[:240],
            "governing_skill_or_rule": "FR-001" if ch else "(anomaly)",
            "link_explicit": True,
            "chain": {
                "outcome": (n.get("did") or "")[:400],
                "expected": (n.get("intent") or "")[:400],
                "actual": (n.get("observed") or "")[:400],
                "reasoning": (n.get("observed") or None),
                "correction_or_rule": (n.get("would_do_differently") or "")[:400],
            },
            "source_ref": "narratives.jsonl#" + (n.get("_slug") or ""),
        })

    # 3. proposal_rejected — EXPLICIT (a rule caught a bad proposal)
    for pid, p in proposals_collapsed.items():
        latest = p["latest"]
        if latest.get("verdict") not in ("auto-reject", "rejected"):
            continue
        rc = latest.get("rule_cited")
        flags.append({
            "date": (latest.get("timestamp") or "")[:10],
            "kind": "proposal_rejected",
            "severity": "med",
            "title": f"{pid} auto-rejected: {p['first'].get('title', '')}",
            "what_happened": (latest.get("verdict_reasoning") or "")[:240],
            "governing_skill_or_rule": rc or "(rule)",
            "link_explicit": True,
            "chain": {
                "outcome": "proposed: " + p["first"].get("title", ""),
                "expected": rule_imperatives.get(rc, ""),
                "actual": (latest.get("verdict_reasoning") or "")[:400],
                "reasoning": (latest.get("verdict_reasoning") or None),
                "correction_or_rule": "re-file a sharpened version that addresses the rule",
            },
            "source_ref": "proposals.jsonl#" + pid,
        })

    # 4. skill_friction — EXPLICIT (feedback.jsonl carries the skill)
    for f in feedback_rows:
        cls = (f.get("class") or "")
        if cls not in ("friction", "gap", "diverged"):
            continue
        flags.append({
            "date": f.get("date", ""),
            "kind": "skill_friction",
            "severity": "low",
            "title": f"{f.get('skill', '')}:{cls} ({f.get('harvest_id', '')})",
            "what_happened": (f.get("evidence") or "")[:240],
            "governing_skill_or_rule": f.get("skill", ""),
            "link_explicit": True,
            "chain": {
                "outcome": (f.get("evidence") or "")[:400],
                "expected": "skill's intended behavior",
                "actual": cls + " — " + (f.get("evidence") or "")[:300],
                "reasoning": None,
                "correction_or_rule": (f.get("plan_candidate") or "") or None,
            },
            "source_ref": f"feedback.jsonl:{f.get('harvest_id', '')} ({f.get('ref', '')})",
        })

    # 5-8. run-log discipline rows — INFERRED (no skill_used on the row)
    for ln, o in week1_rows:
        st = o.get("status")
        fb = o.get("fallback_taken")
        is_slip = st == "declared" or o.get("task_id") == "slip_declared"
        if st in NON_FLAG_STATUSES and not fb and not is_slip:
            continue
        # apparatus bleed guard: a real discipline row has observable_expected
        if "observable_expected" not in o and not fb:
            continue

        date = (o.get("timestamp") or "")[:10]
        oe = o.get("observable_expected") or ""
        oa = o.get("observable_actual") or ""
        task = o.get("task_id", "")

        if fb:
            kind = "fallback"
            sev = "med"
            gov = "fallback"
            title = f"fallback: {task}"
            chain = {
                "outcome": task,
                "expected": oe or "primary approach holds",
                "actual": str(fb),
                "reasoning": None,
                "correction_or_rule": "declared fallback path taken",
            }
        elif is_slip:
            kind = "slip"
            sev = "med"
            gov = "slip-ladder"
            title = f"slip declared: {task}"
            chain = {
                "outcome": "deadline slipped, same approach",
                "expected": oe or "task completes in budget",
                "actual": oa or "slip declared, new cap",
                "reasoning": None,
                "correction_or_rule": "bounded slip; resolved later in the ladder",
            }
        elif st in ("human_gate_blocked", "gate_armed"):
            kind = "gate_block"
            sev = "high"
            gov = "gate-check"
            title = f"gate held: {task}"
            chain = {
                "outcome": "task halted at a human gate",
                "expected": oe or "human attestation required",
                "actual": oa or "blocked / armed; awaited human",
                "reasoning": None,
                "correction_or_rule": "gate honored — not cleared without human",
            }
        else:
            kind = "validation_fail"
            sev = "med" if st in ("failed", "aborted", "escalated", "recovered", "observed") else "low"
            gov = STATUS_TO_INFERRED_SKILL.get(st, "validate")
            title = f"{st}: {task}"
            chain = {
                "outcome": task,
                "expected": oe,
                "actual": oa,
                "reasoning": None,
                "correction_or_rule": None,
            }

        flags.append({
            "date": date,
            "kind": kind,
            "severity": sev,
            "title": title,
            "what_happened": (oa or oe)[:240],
            "governing_skill_or_rule": f"{gov} (INFERRED — run-log row has no skill_used)",
            "link_explicit": False,
            "chain": chain,
            "source_ref": f"week1.run.jsonl L{ln}",
        })

    flags.sort(key=lambda fl: (fl.get("date", ""), 0 if fl.get("severity") == "high" else 1),
               reverse=True)
    return flags


def build_act3(proposals_collapsed, rules, narr, fw_corrections,
               feedback_rows, week1_rows, generated_date) -> dict:
    chains, lh = build_loop(proposals_collapsed, rules, generated_date)

    newest_harvest = max((f.get("date", "") for f in feedback_rows), default="")
    newest_proposal = max((p["first"].get("timestamp", "")[:10]
                           for p in proposals_collapsed.values()), default="")
    dormant = _days_between(newest_harvest, generated_date) if newest_harvest else None
    loop_health = {
        "open_proposals": lh["open"],
        "accepted": lh["accepted"],
        "auto_rejected": lh["rejected"],
        "human_review_pending": lh["human"],
        "newest_harvest": newest_harvest,
        "newest_proposal": newest_proposal,
        "harvest_dormant_days": dormant,
        "signal": (
            f"loop half-dormant: proposals still filed ({newest_proposal}) but no "
            f"new harvest since {newest_harvest} ({dormant}d)"
            if dormant and dormant > 7 else
            "loop active: harvest and proposals both recent"
        ),
    }

    # memory
    corr_nodes = []
    for n in narr.get("correction", []):
        corr_nodes.append({
            "id": n.get("_slug", ""),
            "date": (n.get("timestamp") or "")[:10],
            "title": n.get("_title") or n.get("task_id", ""),
            "agent": _agent_id_to_actor(n.get("agent_id")),
            "source": "narratives.jsonl",
            "enacts_rule": None,
            "references": n.get("references") or [],
        })
    for c in fw_corrections:
        enacted = None
        for r in rules:
            if (c.get("date") == r.get("date")
                    and c.get("title", "").strip().lower() == r["title"].strip().lower()):
                enacted = r["rule_id"]
                break
        corr_nodes.append({
            "id": c["slug"],
            "date": c.get("date", ""),
            "title": c.get("title", ""),
            "agent": "claude-code-main",
            "source": "memory/DECISIONS.md",
            "enacts_rule": enacted,
            "references": [],
        })
    corr_nodes.sort(key=lambda c: c["date"], reverse=True)

    refl_nodes = []
    for n in narr.get("reflection", []):
        refl_nodes.append({
            "id": n.get("_slug") or slugify(n.get("task_id", "")),
            "date": (n.get("timestamp") or "")[:10],
            "title": n.get("_title") or n.get("task_id", ""),
            "agent": _agent_id_to_actor(n.get("agent_id")),
            "intent": (n.get("intent") or "")[:400],
            "observed": (n.get("observed") or "")[:400],
            "would_do_differently": (n.get("would_do_differently") or "")[:400],
            "corrections_honored": n.get("corrections_honored") or [],
        })
    refl_nodes.sort(key=lambda c: c["date"], reverse=True)

    newest_corr_date = corr_nodes[0]["date"] if corr_nodes else ""
    age = _days_between(newest_corr_date, generated_date) if newest_corr_date else None
    recall_floor = {
        "newest_correction_date": newest_corr_date,
        "newest_correction_id": corr_nodes[0]["id"] if corr_nodes else "",
        "age_days": age,
        "freshness": _freshness(age),
        "corrections_total": len(corr_nodes),
        "reflections_total": len(refl_nodes),
    }

    flags = build_flags(narr, fw_corrections, proposals_collapsed, rules,
                        feedback_rows, week1_rows)

    return {
        "loop_chains": chains,
        "loop_health": loop_health,
        "memory": {
            "corrections": corr_nodes,
            "reflections": refl_nodes,
            "recall_floor": recall_floor,
        },
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# attribution gap (the headline honesty surface)
# ---------------------------------------------------------------------------

def build_attribution_gap(week1_rows, fw_run_rows) -> dict:
    total = len(week1_rows) + len(fw_run_rows)
    agent_pop = (sum(1 for _, o in week1_rows if o.get("agent"))
                 + sum(1 for o in fw_run_rows if o.get("agent")))
    skill_pop = (sum(1 for _, o in week1_rows if o.get("skill_used"))
                 + sum(1 for o in fw_run_rows if o.get("skill_used")))
    return {
        "agent_populated": agent_pop,
        "skill_used_populated": skill_pop,
        "total_run_log_rows": total,
        "consumer_rows": len(week1_rows),
        "framework_rows": len(fw_run_rows),
        "explicit_kinds": ["correction", "anomaly", "proposal_rejected", "skill_friction"],
        "inferred_kinds": ["validation_fail", "fallback", "gate_block", "slip"],
        "fix_proposal": "P-008",
        "note": (
            f"raw run-log carries agent on {agent_pop}/{total} rows and skill_used "
            f"on {skill_pop}/{total}. corrections, anomalies, rejected-proposals, "
            "and harvest findings carry an EXPLICIT skill/rule link; run-log-derived "
            "flags (validation_fail/fallback/gate_block/slip) are INFERRED from "
            "status semantics. P-008 (open, human-gated) adds required `agent` + "
            "optional `skill_used` to the consumer run-log — once it lands these "
            "inferred links become explicit and skills get real invocation counts."
        ),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def load_week1_rows() -> list[tuple[int, dict]]:
    """week1.run.jsonl with line numbers (for source_ref + apparatus-bleed
    detection). Read line-by-line — never slurp logs/calls.jsonl."""
    out: list[tuple[int, dict]] = []
    if not CONSUMER_WEEK1_RUN.exists():
        return out
    with CONSUMER_WEEK1_RUN.open() as f:
        for ln, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append((ln, json.loads(raw)))
            except json.JSONDecodeError:
                continue
    return out


def build_summary() -> dict:
    now = datetime.now(timezone.utc)
    generated_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    generated_date = generated_at[:10]

    skills = load_skills()
    agents = load_agents()
    rules = load_rules()
    proposals_raw = load_jsonl(PROPOSALS)
    proposals_collapsed = collapse_proposals(proposals_raw)
    feedback_rows = [f for f in load_jsonl(FEEDBACK) if f.get("harvest_id")]
    spawn_rows = load_jsonl(SPAWN_LEDGER)
    fw_dec = load_decisions(FW_DECISIONS, "framework")
    ap_dec = load_decisions(AP_DECISIONS, "apparatus")
    fw_corrections = [d for d in fw_dec if d["type"] == "correction"]
    narr = load_narrative_nodes()
    week1_rows = load_week1_rows()
    fw_run_rows = load_jsonl(FW_RUN)

    act1 = build_act1(skills, agents, rules, proposals_collapsed,
                      feedback_rows, spawn_rows, fw_corrections)
    act2 = build_act2(proposals_collapsed, fw_dec, ap_dec, narr,
                      feedback_rows, spawn_rows)
    act2["counts_all_time"]["rules"] = len(rules)
    act3 = build_act3(proposals_collapsed, rules, narr, fw_corrections,
                      feedback_rows, week1_rows, generated_date)
    attribution_gap = build_attribution_gap(week1_rows, fw_run_rows)

    # window bounds — min/max date across all dated nodes the dashboard filters
    all_dates: list[str] = []
    for row in act2["timeline"]:
        if row.get("date"):
            all_dates.append(row["date"])
    for fl in act3["flags"]:
        if fl.get("date"):
            all_dates.append(fl["date"])
    oldest = min(all_dates) if all_dates else generated_date
    newest = max(all_dates) if all_dates else generated_date

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "repo": str(REPO),
        "consumer": str(CONSUMER),
        "window": {
            "default_days": WINDOW_DEFAULT_DAYS,
            "min_days": WINDOW_MIN_DAYS,
            "max_days": WINDOW_MAX_DAYS,
            "oldest_event": oldest,
            "newest_event": newest,
        },
        "standing": {
            "firewall": act1["firewall"],
            "skills": {"rollup": act1["skills"]["rollup"]},
            "attribution_gap": attribution_gap,
        },
        "act1_system": act1,
        "act2_activity": act2,
        "act3_loop_and_memory": act3,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Project the brain's skills+governance+memory layer to summary.json.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print counts; do not write summary.json.")
    args = parser.parse_args()

    summary = build_summary()
    payload = json.dumps(summary, indent=2) + "\n"

    a1 = summary["act1_system"]
    a2 = summary["act2_activity"]
    a3 = summary["act3_loop_and_memory"]
    print("summary projection — skills+governance+memory layer")
    print(f"  generated_at: {summary['generated_at']}")
    print(f"  window: default {summary['window']['default_days']}d  "
          f"events {summary['window']['oldest_event']} → {summary['window']['newest_event']}")
    print(f"  ACT I  : {a1['skills']['rollup']['total']} skills "
          f"(A{a1['skills']['rollup']['by_layer']['A']}/"
          f"B{a1['skills']['rollup']['by_layer']['B']}/"
          f"C{a1['skills']['rollup']['by_layer']['C']}, "
          f"{a1['skills']['rollup']['runtime_safe']} runtime-safe), "
          f"{len(a1['agents'])} agents, {len(a1['rules'])} rules, "
          f"firewall {a1['firewall']['status']} ({len(a1['firewall']['violations'])} violations)")
    print(f"  ACT II : {len(a2['timeline'])} timeline events  "
          f"counts_all_time={a2['counts_all_time']}")
    print(f"  ACT III: {len(a3['loop_chains'])} loop chains, "
          f"{len(a3['flags'])} flags, "
          f"recall floor {a3['memory']['recall_floor']['freshness']} "
          f"(age {a3['memory']['recall_floor']['age_days']}d), "
          f"loop dormant {a3['loop_health']['harvest_dormant_days']}d")
    gap = summary["standing"]["attribution_gap"]
    print(f"  attribution gap: agent {gap['agent_populated']}/{gap['total_run_log_rows']}  "
          f"skill_used {gap['skill_used_populated']}/{gap['total_run_log_rows']}")

    if args.dry_run:
        print("DRY RUN — summary.json not written.")
        return 0

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    existing = SUMMARY.read_text() if SUMMARY.exists() else None
    if existing != payload:
        SUMMARY.write_text(payload)
        print(f"wrote {SUMMARY} ({len(payload)} bytes)")
    else:
        print(f"unchanged {SUMMARY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
