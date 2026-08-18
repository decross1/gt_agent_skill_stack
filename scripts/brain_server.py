#!/usr/bin/env python3
"""Dynamic brain backend — serves the static view dir AND a small JSON API that
makes proposal review conversational and frictionless.

Smallest-slice scope (S25): one focused proposal-review loop —
  GET  /api/proposals                 list open framework proposals
  GET  /api/proposal/<id>             proposal + card + discussion + amended_draft
  POST /api/proposal/<id>/discuss     {message}  -> Gemma turn (amend dialogue)
  POST /api/proposal/<id>/synthesize  -> Gemma turns the discussion into a crisp
                                         amended proposal 'change'; persists it
  POST /api/proposal/<id>/verdict     {verdict,note,basis,actor_id,amended_change?} -> exec
                                         blessed CLI; on accept auto-writes handoff
  POST /api/proposal/<id>/handoff     {basis,actor_id} -> write handoffs/<id>.md

Design invariants (keep the brain honest while making it dynamic):
- Files stay canonical. Gemma is a drafting assistant; every output is written
  through to append-only ledgers (proposal_cards.jsonl) — projection/regen reads
  the stored fields, never calls the model.
- Verdicts go through the blessed CLI (review_proposal_cli.py) via argv, no shell.
- Dev-time only, bound to 127.0.0.1. The brain firewall (BOUNDARY.md) keeps this
  out of any apparatus runtime.

Run: python3 scripts/brain_server.py [--port 5180]
"""
import argparse
import json
import os
import re
import selectors
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brain_ledger import accepted_decision, read_proposals

ROOT = Path(__file__).resolve().parent.parent
VIEW = ROOT / "memory" / "brain" / "view"
PROPOSALS = ROOT / "memory" / "brain" / "proposals.jsonl"
CARDS = ROOT / "memory" / "brain" / "proposal_cards.jsonl"
FEEDBACK = ROOT / "memory" / "feedback.jsonl"
RULES = ROOT / "memory" / "brain" / "rules.md"
SKILLS = ROOT / ".agents" / "skills"
HANDOFFS = ROOT / "handoffs"
CLI = ROOT / "scripts" / "review_proposal_cli.py"
FRAMEWORK_STATE = ROOT / "run_state" / "framework.state.json"
FRAMEWORK_RUN = ROOT / "run_state" / "framework.run.jsonl"
WATCH_PID = ROOT / "run_state" / "brain-watch.pid"
WATCH_LOG = ROOT / "run_state" / "brain-watch.log"
SUMMARY_JSON = VIEW / "summary.json"

GEMMA_URL = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "gemma-4-26b-a4b"
PID_RE = re.compile(r"^P-\d+$")

# The review UI is an assertion surface, not an authentication boundary.  Keep
# its actor vocabulary closed so a caller cannot forge arbitrary attribution.
ACTORS = {
    "derrick": {
        "id": "derrick",
        "type": "human",
        "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    },
    "oracle": {
        "id": "oracle",
        "type": "agent",
        "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    },
}


def actor_record(actor_id: str) -> dict:
    """Return a fresh structured closed actor record or reject the input."""
    if not isinstance(actor_id, str) or actor_id not in ACTORS:
        raise ValueError("actor_id must be one of: derrick, oracle")
    return dict(ACTORS[actor_id])

# Serializes the read-then-append in generate_card so a card is written through
# to proposal_cards.jsonl exactly once even under ThreadingHTTPServer concurrency.
_CARD_LOCK = threading.Lock()
# Serializes verdict-triggered projection regens so two concurrent refreshes
# cannot tear summary.json / map_data.js with interleaved writes.
_REGEN_LOCK = threading.Lock()

# In-process caches for the live projections (GET /api/summary, /api/map). A short
# TTL coalesces bursts (rapid reloads, many tabs polling every ~30s) into one build
# while keeping staleness far under the poll interval.
_SUMMARY_TTL_S = 3.0
_SUMMARY_LOCK = threading.Lock()
_summary_cache = {"mono": 0.0, "data": None}
_MAP_LOCK = threading.Lock()
_map_cache = {"mono": 0.0, "data": None}

# The operations view is deliberately an observation surface, not a controller.
# Its work has an explicit resource ceiling so a stale/broken local installation
# cannot turn a dashboard poll into an unbounded filesystem or subprocess walk.
OPS_FILE_BYTES = 1_048_576
OPS_LOG_TAIL_BYTES = 65_536
OPS_CURSOR_BYTES = 16 * 1_024 * 1_024
OPS_SUBPROCESS_TIMEOUT_S = 2
OPS_TOTAL_BUDGET_S = 3
OPS_CACHE_TTL_S = 1.0
OPS_MAX_LIFECYCLE_PROPOSALS = 12
_LOG_TS = re.compile(r"^\[([^\]]+)\]")
_FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPS_LOCK = threading.Lock()
_ops_cache = {"mono": 0.0, "data": None}


class GemmaError(RuntimeError):
    """Raised when the Gemma drafting assistant is unreachable, times out, or
    returns an unusable response. Carries a client-safe message only — the raw
    exception detail (URLs, stack) is logged server-side, never surfaced."""

# project_summary supplies the framework/research scope classifier + live summary;
# project_map supplies the live cluster-map projection. Both read the ledgers
# directly and are deterministic (no LLM) — safe to compute per request.
sys.path.insert(0, str(ROOT / "scripts"))
import project_summary as ps  # noqa: E402
import project_map as pm  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def gemma(messages: list[dict], max_tokens: int = 700, temperature: float = 0.3) -> str:
    """Call the Gemma drafting assistant (OpenAI-compatible chat) and return the
    reply text. Any transport, timeout, HTTP, or malformed-response failure is
    re-raised as GemmaError with a client-safe message so callers can map it to a
    clean JSON 5xx instead of crashing the request thread or leaking internals."""
    body = json.dumps({"model": MODEL, "messages": messages,
                       "max_tokens": max_tokens, "temperature": temperature}).encode()
    req = urllib.request.Request(GEMMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.loads(r.read())
        return d["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        # Server-side detail to stderr; client sees only the generic message.
        print(f"gemma: upstream HTTP {e.code}", file=sys.stderr)
        raise GemmaError("drafting assistant returned an error") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        print(f"gemma: unreachable ({type(e).__name__})", file=sys.stderr)
        raise GemmaError("drafting assistant unavailable") from e
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        print(f"gemma: bad response ({type(e).__name__})", file=sys.stderr)
        raise GemmaError("drafting assistant returned an unusable response") from e


def strip_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


# ---------------------------------------------------------------------------
# proposal data
# ---------------------------------------------------------------------------

def open_framework_proposals() -> list[dict]:
    collapsed = ps.collapse_proposals(jsonl(PROPOSALS))
    out = []
    for pid, p in collapsed.items():
        # lifecycle_state (not final_verdict) is the gate: a draft has no verdict
        # and would otherwise read as "open" and leak into the review queue.
        if ps.lifecycle_state(p) not in ("open", "human-review"):
            continue
        if ps.proposal_scope(p["first"], "a_bgt_rsi") != "framework":
            continue
        f = p["first"]
        out.append({"proposal_id": pid, "title": f.get("title", ""),
                    "target": f.get("target", ""), "target_type": f.get("target_type", ""),
                    "verdict": ps.final_verdict(p)})
    out.sort(key=lambda x: x["proposal_id"])
    return out


def proposal_first(pid: str) -> dict | None:
    collapsed = ps.collapse_proposals(jsonl(PROPOSALS))
    return collapsed.get(pid, {}).get("first")


def stored_card(pid: str) -> dict | None:
    card = None
    for r in jsonl(CARDS):
        if r.get("proposal_id") == pid and r.get("kind") == "card":
            card = r
    return card


def discussion(pid: str) -> list[dict]:
    return [{"role": r["role"], "content": r["content"], "ts": r.get("ts")}
            for r in jsonl(CARDS)
            if r.get("proposal_id") == pid and r.get("kind") == "discuss"]


def context_for(first: dict) -> str:
    """Plain-text context bundle: target skill, drift evidence, active rules."""
    parts = []
    target, ttype = first.get("target", ""), first.get("target_type", "")
    skill_md = SKILLS / target / "SKILL.md"
    if ttype == "skill" and skill_md.exists():
        parts.append(f"=== TARGET SKILL ({target}) ===\n" + skill_md.read_text()[:3000])
    findings = [f for f in jsonl(FEEDBACK) if f.get("skill") == target]
    if findings:
        ev = "\n".join(f"- [{f['class']}] {f['evidence'][:200]}" for f in findings[-8:])
        parts.append(f"=== DRIFT EVIDENCE (harvest findings on {target}) ===\n" + ev)
    if RULES.exists():
        parts.append("=== ACTIVE RULES ===\n" + RULES.read_text()[:1500])
    return "\n\n".join(parts) or "(no extra context)"


def generate_card(first: dict) -> dict:
    """Draft a review card for a proposal via Gemma and append it to
    proposal_cards.jsonl exactly once. A re-GET reads the stored card (see
    stored_card) and never calls the model again. The _CARD_LOCK guard makes the
    read-then-append atomic so concurrent first-GETs do not double-write; a raised
    GemmaError propagates to the handler and NO partial card is persisted."""
    pid = first.get("proposal_id")
    with _CARD_LOCK:
        # Double-checked: another thread may have generated it while we waited.
        existing = stored_card(pid)
        if existing:
            return existing
        return _draft_and_store_card(first)


def _draft_and_store_card(first: dict) -> dict:
    sys_p = (
        "You help a Derrick-or-Oracle steward review proposals to improve the agent_system framework "
        "(a portable skills+memory framework). For the given proposal, return STRICT "
        "JSON only (no prose, no code fence) with keys: "
        '"means" (1-3 plain sentences: what this proposal actually means), '
        '"pros_accept" (array of short strings), "cons_accept" (array), '
        '"pros_reject" (array), "cons_reject" (array), '
        'and "rule_check" (object: {"conflict": bool, "rule": "FR-NNN or null", '
        '"why": "short"} — does it directly conflict with an ACTIVE RULE listed in context?). '
        "Be concrete and specific to THIS proposal; 2-4 bullets per array."
    )
    user_p = (
        f"PROPOSAL {first.get('proposal_id')}\n"
        f"title: {first.get('title')}\n"
        f"target: {first.get('target_type')}:{first.get('target')}\n"
        f"change: {first.get('change')}\n"
        f"reasoning: {first.get('reasoning')}\n\n"
        f"{context_for(first)}"
    )
    raw = gemma([{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_p}], max_tokens=800, temperature=0.2)
    try:
        data = json.loads(strip_fence(raw))
    except json.JSONDecodeError:
        data = {"means": strip_fence(raw)[:600], "pros_accept": [], "cons_accept": [],
                "pros_reject": [], "cons_reject": [],
                "rule_check": {"conflict": False, "rule": None, "why": "parse-fallback"}}
    card = {"kind": "card", "proposal_id": first.get("proposal_id"),
            "generated_at": _now(), "model": MODEL,
            "means": data.get("means", ""),
            "pros_accept": data.get("pros_accept", []), "cons_accept": data.get("cons_accept", []),
            "pros_reject": data.get("pros_reject", []), "cons_reject": data.get("cons_reject", []),
            "rule_check": data.get("rule_check", {})}
    with CARDS.open("a") as f:
        f.write(json.dumps(card) + "\n")
    return card


def append_discuss(pid: str, role: str, content: str) -> None:
    with CARDS.open("a") as f:
        f.write(json.dumps({"kind": "discuss", "proposal_id": pid, "ts": _now(),
                            "role": role, "content": content}) + "\n")


def discuss_turn(first: dict, message: str) -> str:
    pid = first.get("proposal_id")
    sys_p = (
        "You help a Derrick-or-Oracle steward refine a proposal to improve the agent_system framework. "
        "The steward may say none of the options look clean, or raise a worry. Engage "
        "concretely: address the worry, and when useful propose a sharper amended "
        "version of the change (quote it). Keep replies tight. Do not claim the change "
        "is implemented — you only help decide and shape it."
    )
    msgs = [{"role": "system", "content": sys_p},
            {"role": "user", "content":
                f"PROPOSAL {pid}: {first.get('title')}\n"
                f"change: {first.get('change')}\n\n{context_for(first)}"}]
    for t in discussion(pid):
        msgs.append({"role": t["role"], "content": t["content"]})
    msgs.append({"role": "user", "content": message})
    reply = gemma(msgs, max_tokens=700, temperature=0.4)
    append_discuss(pid, "user", message)
    append_discuss(pid, "assistant", reply)
    return reply


def latest_amended_draft(pid: str) -> dict | None:
    """Return the LATEST amended_draft entry for a proposal, or None. The ledger
    is append-only; a re-synthesis or human-edited accept appends a fresh row, so
    the last matching line wins (mirrors stored_card's last-write-wins read)."""
    draft = None
    for r in jsonl(CARDS):
        if r.get("proposal_id") == pid and r.get("kind") == "amended_draft":
            draft = r
    return draft


def append_amended_draft(pid: str, change: str) -> dict:
    """Append-only write of an amended_draft entry; returns the stored row."""
    row = {"kind": "amended_draft", "proposal_id": pid, "generated_at": _now(),
           "model": MODEL, "change": change}
    with CARDS.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return row


def _strip_proposal_scaffold(text: str) -> str:
    """Conservative cleanup of a synthesized amended draft. Gemma 4 sometimes
    echoes the input scaffold (`PROPOSAL <id>: ... / target: ... / change: ...`)
    despite the prompt forbidding it. Only when the reply actually begins with that
    echoed header do we keep the text after the echoed `change:` label; we also drop
    a lone leading `change:` / `amended change:` label. Clean replies pass through
    untouched, so this never mangles a well-formed draft."""
    t = strip_fence(text).strip()
    if re.match(r"(?is)^\s*PROPOSAL\b", t):
        m = re.search(r"(?im)^\s*change:\s*", t)
        if m:
            t = t[m.end():].strip()
    t = re.sub(r"(?is)^\s*(amended\s+)?change:\s*", "", t)
    return t.strip()


def synthesize_amended(first: dict) -> str:
    """Ask Gemma to fold the ORIGINAL proposal change + the discussion thread into
    a CRISP, self-contained amended proposal 'change' — plain prose, the final
    proposal text only (no chat framing, no "here's how to rewrite"). Persists an
    amended_draft entry (append-only) and returns the change text. A GemmaError
    propagates so the handler maps it to a clean 5xx and NOTHING is persisted."""
    pid = first.get("proposal_id")
    disc = discussion(pid)
    disc_txt = "\n".join(f"{t['role']}: {t['content']}" for t in disc) or "(no discussion)"
    sys_p = (
        "You refine a proposal to improve the agent_system framework. Fold the "
        "ORIGINAL proposal change together with the discussion below into a single "
        "CRISP, self-contained amended proposal. Return ONLY the final proposal "
        "text — the new 'change' as it would be recorded. Plain prose, no chat "
        "framing, no preamble, no 'here is how to rewrite it', no quotes around the "
        "whole thing. Just the amended proposal itself. Do NOT begin your answer "
        "with 'PROPOSAL', a title line, 'target:', or 'change:' — write the "
        "proposal body directly."
    )
    user_p = (
        f"PROPOSAL {pid}: {first.get('title')}\n"
        f"target: {first.get('target_type')}:{first.get('target')}\n"
        f"ORIGINAL change: {first.get('change')}\n"
        f"reasoning: {first.get('reasoning')}\n\n"
        f"DISCUSSION:\n{disc_txt}"
    )
    raw = gemma([{"role": "system", "content": sys_p},
                 {"role": "user", "content": user_p}], max_tokens=800, temperature=0.3)
    change = _strip_proposal_scaffold(raw)
    append_amended_draft(pid, change)
    return change


def canonical_accepted_decision(pid: str) -> dict | None:
    """Read one verified self-contained acceptance from the canonical ledger.

    An old/tampered accepted decision has no safe reconstruction path.  It is an
    error, not permission to substitute an ignored card or a current filing.
    """
    return accepted_decision(read_proposals(PROPOSALS), pid)


def canonical_decision_actor(decision: dict, requested_actor_id: str | None) -> dict:
    """Verify decision attribution before emitting a recovery handoff."""
    stored = decision.get("actor")
    if not isinstance(stored, dict):
        raise ValueError("accepted decision has invalid actor")
    try:
        canonical = actor_record(stored.get("id"))
    except ValueError as exc:
        raise ValueError("accepted decision has invalid actor") from exc
    if stored != canonical:
        raise ValueError("accepted decision actor does not match closed identity")
    if requested_actor_id is not None and actor_record(requested_actor_id) != canonical:
        raise ValueError("handoff actor cannot override accepted decision actor")
    return canonical


def write_handoff(first: dict, basis: str = "original", actor_id: str | None = None) -> str:
    pid = first.get("proposal_id")
    decision = canonical_accepted_decision(pid)
    if decision is not None:
        # This is the recovery path: use the exact accepted body and independently
        # re-validated digest, never a mutable/ignored card draft or current UI text.
        basis = decision.get("basis", "original")
        body_label = "Accepted amended proposal (canonical)" if basis == "amended" else \
            "Accepted original proposal (canonical)"
        body_text = decision["accepted_body"]
        body_digest = decision["accepted_body_sha256"]
        actor = canonical_decision_actor(decision, actor_id)
    else:
        actor = actor_record(actor_id) if actor_id is not None else None
        body_digest = None
        # Compatibility for manually requested pre-acceptance drafts. Once an
        # acceptance exists, the canonical branch above is mandatory.
        amended = latest_amended_draft(pid) if basis == "amended" else None
        if amended:
            body_label = "Amended proposal (final form)"
            body_text = amended.get("change", "")
        else:
            body_label = "Original proposal (verbatim)"
            body_text = first.get("change", "")
    # Handoff recovery must not depend on ignored, model-authored card material.
    card = stored_card(pid) or {}
    disc = discussion(pid)
    disc_txt = "\n".join(f"**{t['role']}:** {t['content']}" for t in disc) or "_(no discussion)_"
    synth = ""
    try:
        synth = gemma([
            {"role": "system", "content":
                "Synthesize non-authoritative implementation context for a dev agent "
                "from this accepted proposal body and its discussion: likely files and "
                "2-4 candidate acceptance criteria. Preserve the accepted scope, label "
                "uncertainty, and do not imply consensus. Markdown, no preamble."},
            {"role": "user", "content":
                f"PROPOSAL {pid}: {first.get('title')}\nchange: {body_text}\n"
                f"reasoning: {first.get('reasoning')}\n\nDISCUSSION:\n{disc_txt}"}
        ], max_tokens=700, temperature=0.2)
    except Exception as e:  # noqa: BLE001
        synth = f"_(synthesis unavailable: {e})_"
    HANDOFFS.mkdir(exist_ok=True)
    actor_line = (
        f"- **Actor:** `{actor['id']}` ({actor['type']}; {actor['authentication']}, "
        "not cryptographically authenticated)\n\n"
        if actor else ""
    )
    digest_line = f"- **Accepted-body SHA-256:** `{body_digest}`\n\n" if body_digest else ""
    authority_note = (
        "> **Authority boundary:** Only the canonical accepted proposal body and its "
        "ledger decision record the accepted transition. Filing rationale, card "
        "interpretation, discussion, and model synthesis below are non-authoritative "
        "context and may be regenerated.\n\n"
        if body_digest else
        "> **Draft boundary:** No canonical acceptance was found. Everything in this "
        "pre-acceptance handoff is non-authoritative review context.\n\n"
    )
    md = (
        f"# Implementation handoff — {pid}\n\n"
        f"_Generated {_now()} by the brain proposal-review loop (basis: {basis}). "
        f"Pass to a dev agent._\n\n"
        f"- **Target:** `{first.get('target_type')}:{first.get('target')}`\n"
        f"- **Title:** {first.get('title')}\n\n"
    ) + actor_line + digest_line + authority_note + (
        f"## {body_label}\n\n{body_text}\n\n"
        f"### Filing rationale (context)\n\n{first.get('reasoning')}\n\n"
        f"## Card interpretation (non-authoritative)\n\n{card.get('means','')}\n\n"
        f"## Discussion (non-authoritative context)\n\n{disc_txt}\n\n"
        f"## Synthesized implementation context (non-authoritative)\n\n{synth}\n"
    )
    path = HANDOFFS / f"{pid}.md"
    path.write_text(md)
    return str(path.relative_to(ROOT))


def record_verdict(pid: str, verdict: str, note: str, basis: str = "original",
                   actor_id: str | None = None, accepted_body: str | None = None) -> dict:
    if verdict not in ("accept", "reject", "needs_revision"):
        return {"ok": False, "error": "bad verdict"}
    if basis not in ("original", "amended"):
        return {"ok": False, "error": "bad basis"}
    try:
        actor_record(actor_id)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    command = [sys.executable, str(CLI), "--proposal-id", pid, "--verdict", verdict,
               "--note", note, "--basis", basis, "--actor", actor_id]
    if accepted_body is not None:
        command.extend(["--accepted-body", accepted_body])
    proc = subprocess.run(
        command,
        capture_output=True, text=True, timeout=30)
    try:
        out = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        out = {"ok": False, "error": proc.stderr.strip() or "cli error"}
    out["exit_code"] = proc.returncode
    return out


def refresh_projection() -> None:
    """Best-effort projection refresh after a framework ledger mutation (a verdict).
    Re-runs the framework-local projectors — project_pages -> project_map ->
    project_summary — so the dashboard inbox / needs-you count, the loop strip, and
    the graph's proposal nodes reflect the just-recorded verdict. Without this, the
    static projection (summary_data.js) lags the live /api/proposals until the next
    regen, and the dashboard shows phantom 'open' proposals the review queue no
    longer lists.

    Deliberately does NOT run ingest_apparatus: re-ingesting the apparatus's
    narratives/edges is needless work on a framework-proposal verdict (the
    projectors still read consumer logs read-only — the firewall-sanctioned
    direction; BOUNDARY.md forbids the reverse, apparatus reading the brain).
    NEVER raises: the verdict is already recorded append-only, and a projection
    hiccup must not turn a recorded decision into an error. Script paths resolve
    via ROOT so tests pointing ROOT at a tmp dir cannot touch the real projection.
    Serialized by _REGEN_LOCK."""
    with _REGEN_LOCK:
        for name in ("project_pages.py", "project_map.py", "project_summary.py"):
            script = ROOT / "scripts" / name
            try:
                r = subprocess.run([sys.executable, str(script)], cwd=str(ROOT),
                                   capture_output=True, text=True, timeout=120)
                if r.returncode != 0:
                    print(f"refresh_projection: {name} exit {r.returncode}", file=sys.stderr)
            except Exception as e:  # noqa: BLE001 — best-effort; never fail the verdict
                print(f"refresh_projection: {name} failed ({type(e).__name__})", file=sys.stderr)


def _schedule_refresh() -> None:
    """Fire refresh_projection on a daemon thread so the verdict response returns
    immediately and the projection catches up within a second or two. Split out so
    tests can stub the scheduling (no subprocess spawn) without touching the
    refresh_projection contract itself."""
    threading.Thread(target=refresh_projection, daemon=True).start()


def current_summary() -> dict:
    """Compute the dashboard summary on demand so the dashboard reflects the
    ledgers at request time instead of a baked file. This is the live counterpart
    of the static summary_data.js: deterministic and identical in content (it calls
    the same project_summary.build_summary the projector uses), and it NEVER calls
    the LLM. A short TTL (_SUMMARY_TTL_S) coalesces concurrent/rapid requests into
    one build; the lock makes a burst wait for a single build rather than starting
    many."""
    with _SUMMARY_LOCK:
        now = time.monotonic()
        c = _summary_cache
        if c["data"] is not None and (now - c["mono"]) < _SUMMARY_TTL_S:
            return c["data"]
        data = ps.build_summary()
        c["data"], c["mono"] = data, now
        return data


def current_map() -> dict:
    """Compute the cluster-map projection on demand — the live counterpart of the
    baked map_data.js (window.BRAIN_MAP). Same deterministic projector the regen
    uses (project_map.build_map); never calls the LLM. TTL-cached like
    current_summary so a poll fleet collapses to one build."""
    with _MAP_LOCK:
        now = time.monotonic()
        c = _map_cache
        if c["data"] is not None and (now - c["mono"]) < _SUMMARY_TTL_S:
            return c["data"]
        data = pm.build_map()
        c["data"], c["mono"] = data, now
        return data


# ---------------------------------------------------------------------------
# read-only operations truth (never controls services or rewrites state)
# ---------------------------------------------------------------------------

def _fact(value, status: str, provenance: str, uncertainty: str = "") -> dict:
    """A small, uniform evidence envelope for the operations endpoint."""
    return {"value": value, "status": status, "provenance": provenance,
            "uncertainty": uncertainty}


def _read_limited(path: Path, limit: int, *, tail: bool = False) -> tuple[str | None, bool, str | None]:
    """Read at most *limit* bytes without following a missing/stale assumption."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fp:
            if tail and size > limit:
                fp.seek(size - limit)
            raw = fp.read(limit + 1)
    except (OSError, ValueError) as exc:
        return None, False, type(exc).__name__
    truncated = size > limit or len(raw) > limit
    if len(raw) > limit:
        raw = raw[-limit:] if tail else raw[:limit]
    return raw.decode("utf-8", errors="replace"), truncated, None


def _load_json_limited(path: Path, limit: int) -> tuple[dict | None, str | None]:
    text, truncated, error = _read_limited(path, limit)
    if error:
        return None, error
    if truncated:
        return None, "byte_limit"
    try:
        value = json.loads(text or "")
    except json.JSONDecodeError:
        return None, "malformed_json"
    return (value, None) if isinstance(value, dict) else (None, "not_object")


def _run_bounded(argv: list[str], *, deadline: float | None = None,
                 env: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """Run a fixed observation command with byte and shared-wall-clock bounds."""
    stop_at = min(deadline, time.monotonic() + OPS_SUBPROCESS_TIMEOUT_S) if deadline else (
        time.monotonic() + OPS_SUBPROCESS_TIMEOUT_S)
    if stop_at <= time.monotonic():
        return None, "budget_exhausted"
    try:
        proc = subprocess.Popen(argv, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    except OSError as exc:
        return None, type(exc).__name__
    chunks: list[bytes] = []
    size = 0
    selector = selectors.DefaultSelector()
    try:
        assert proc.stdout is not None
        selector.register(proc.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = stop_at - time.monotonic()
            if remaining <= 0:
                proc.kill()
                proc.wait()
                return None, "TimeoutExpired"
            for key, _ in selector.select(remaining):
                block = os.read(key.fileobj.fileno(), min(8192, OPS_FILE_BYTES - size + 1))
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                size += len(block)
                if size > OPS_FILE_BYTES:
                    proc.kill()
                    proc.wait()
                    return None, "byte_limit"
                chunks.append(block)
        remaining = stop_at - time.monotonic()
        if remaining <= 0:
            proc.kill()
            proc.wait()
            return None, "budget_exhausted"
        if proc.wait(timeout=remaining) != 0:
            return None, f"exit_{proc.returncode}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        proc.kill()
        proc.wait()
        return None, type(exc).__name__
    finally:
        selector.close()
    return b"".join(chunks).decode("utf-8", errors="replace"), None


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # Local/naive timestamps cannot be compared honestly with the UTC observer.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _watcher_observation(warnings: list[str]) -> dict:
    raw, truncated, error = _read_limited(WATCH_PID, 128)
    if error:
        return {"state": _fact("unknown", "unknown", "run_state/brain-watch.pid",
                                f"pidfile unavailable: {error}")}
    pid_text = (raw or "").strip()
    if truncated or not pid_text.isdecimal() or int(pid_text) <= 0:
        warnings.append("watcher pidfile malformed or exceeds its bounded format")
        return {"state": _fact("unknown", "unknown", "run_state/brain-watch.pid",
                                "pidfile is not one positive decimal PID")}
    pid = int(pid_text)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return {"state": _fact("stale", "stale", "pidfile + kill(0)",
                                "PID no longer exists; no watcher inferred")}
    except PermissionError:
        return {"state": _fact("unknown", "unknown", "pidfile + kill(0)",
                                "process exists but cannot be inspected")}
    except OSError as exc:
        return {"state": _fact("unknown", "unknown", "pidfile + kill(0)", type(exc).__name__)}
    cmdline, cmd_truncated, cmd_error = _read_limited(Path(f"/proc/{pid}/cmdline"), 8192)
    if cmd_error or cmd_truncated:
        return {"state": _fact("unknown", "unknown", "pidfile + /proc cmdline",
                                "live PID could not be boundedly matched to watch_brain.py")}
    # A live PID alone is not proof: PID reuse is common enough to require the
    # expected script token before presenting it as a watcher.
    expected = str(ROOT / "scripts" / "watch_brain.py")
    argv = (cmdline or "").split("\x00")
    if expected not in argv:
        warnings.append("watcher pid is alive but its command does not match watch_brain.py")
        return {"state": _fact("stale", "stale", "pidfile + /proc cmdline",
                                "PID is live but may have been recycled")}
    return {"state": _fact("alive", "observed", "pidfile + /proc cmdline",
                            "process liveness does not prove a successful pipeline"),
            "pid": _fact(pid, "observed", "run_state/brain-watch.pid", "local PID only")}


def _pipeline_observation(warnings: list[str]) -> dict:
    text, truncated, error = _read_limited(WATCH_LOG, OPS_LOG_TAIL_BYTES, tail=True)
    if error:
        unknown = _fact(None, "unknown", "run_state/brain-watch.log", f"log unavailable: {error}")
        return {"last_success": unknown, "last_failure": unknown}
    success = failure = None
    malformed = 0
    for line in (text or "").splitlines():
        if "pipeline ok" not in line and "pipeline FAIL" not in line:
            continue
        match = _LOG_TS.match(line)
        timestamp = _parse_timestamp(match.group(1)) if match else None
        if timestamp is None:
            malformed += 1
            continue
        item = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if "pipeline ok" in line:
            success = item
        if "pipeline FAIL" in line:
            failure = item
    if malformed:
        warnings.append(f"{malformed} malformed pipeline log line(s) ignored")
    suffix = "log tail is truncated; older events are unknown" if truncated else ""
    return {
        "last_success": _fact(success, "observed" if success else "unknown",
                              "bounded watcher log tail", suffix or "no parseable success in tail"),
        "last_failure": _fact(failure, "observed" if failure else "unknown",
                              "bounded watcher log tail", suffix or "no parseable failure in tail"),
        "tail": _fact({"bytes_limit": OPS_LOG_TAIL_BYTES, "truncated": truncated},
                      "observed", "run_state/brain-watch.log", "tail only"),
    }


def _projection_observation(warnings: list[str]) -> dict:
    payload, error = _load_json_limited(SUMMARY_JSON, OPS_FILE_BYTES)
    if error:
        warnings.append(f"projection summary unavailable: {error}")
        unknown = _fact(None, "unknown", "memory/brain/view/summary.json", error)
        return {"generated_at": unknown, "age_seconds": unknown}
    timestamp = _parse_timestamp(payload.get("generated_at"))
    if timestamp is None:
        warnings.append("projection summary has no parseable generated_at")
        unknown = _fact(None, "unknown", "summary.json generated_at", "missing or malformed timestamp")
        return {"generated_at": unknown, "age_seconds": unknown}
    now = datetime.now(timezone.utc)
    generated = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "generated_at": _fact(generated, "observed", "summary.json", "static projection; not live API"),
        "age_seconds": _fact(max(0, int((now - timestamp).total_seconds())), "observed",
                             "UTC now minus summary.json generated_at", "clock skew is clamped at zero"),
    }


def _count_lines_bounded(path: Path, limit: int, *, deadline: float) -> tuple[int | None, str | None]:
    """Count lines without retaining the consumer log; fail closed on cap/time."""
    try:
        if path.stat().st_size > limit:
            return None, "byte_limit"
        total = 0
        lines = 0
        last = b""
        with path.open("rb") as fp:
            while True:
                if time.monotonic() >= deadline:
                    return None, "budget_exhausted"
                block = fp.read(65_536)
                if not block:
                    break
                total += len(block)
                if total > limit:
                    return None, "byte_limit"
                lines += block.count(b"\n")
                last = block[-1:]
    except OSError as exc:
        return None, type(exc).__name__
    return lines + int(total > 0 and last != b"\n"), None


def _cursor_observation(warnings: list[str], *, deadline: float) -> dict:
    state, state_error = _load_json_limited(FRAMEWORK_STATE, OPS_FILE_BYTES)
    watermark = (state or {}).get("harvest_watermark", {}).get("a_bgt_rsi")
    recorded = watermark.get("run_jsonl_lines") if isinstance(watermark, dict) else None
    if not isinstance(recorded, int):
        warnings.append(f"framework harvest cursor unavailable: {state_error or 'missing watermark'}")
        framework = _fact(None, "unknown", "run_state/framework.state.json", state_error or "missing watermark")
        return {"framework_harvest": framework,
                "consumer": _fact(None, "unknown", "consumer cursor", "no comparable cursor")}
    # Keep the payload deliberately narrow: cursor numbers only, never adjacent
    # state metadata such as commit IDs or decision labels.
    framework = _fact({"run_jsonl_lines": recorded}, "observed", "run_state/framework.state.json",
                      "declared harvest watermark, not proof of current consumer state")
    consumer = ps.resolve_consumer()
    current_path = consumer / "run_state" / "week1.run.jsonl" if consumer else None
    current_lines, current_error = (_count_lines_bounded(current_path, OPS_CURSOR_BYTES, deadline=deadline)
                                    if current_path else (None, "consumer_unresolved"))
    if current_lines is None:
        return {"framework_harvest": framework,
                "consumer": _fact(None, "unknown", "consumer run_state/week1.run.jsonl",
                                  current_error or "watermark has no numeric run_jsonl_lines")}
    return {"framework_harvest": framework,
            "consumer": _fact({"lines": current_lines, "watermark_lines": recorded,
                                "delta_lines": current_lines - recorded},
                               "observed", "bounded consumer line count + framework watermark",
                               "delta measures only this file; it is not unprocessed-work proof")}


def _proposal_rows_bounded(warnings: list[str]) -> tuple[list[dict], str, int]:
    text, truncated, error = _read_limited(PROPOSALS, OPS_FILE_BYTES)
    if error:
        warnings.append(f"proposal ledger unavailable: {error}")
        return [], "unknown", 1
    rows: list[dict] = []
    bad = 0
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        # Keep mixed or unsupported rows visible as warnings rather than handing
        # them to the projector, which historically skips rows without an ID.
        if (not isinstance(row, dict) or not isinstance(row.get("proposal_id"), str)
                or not _parse_timestamp(row.get("timestamp"))
                or not any(key in row for key in ("status", "verdict", "change", "enactment", "verification"))):
            bad += 1
            continue
        rows.append(row)
    if bad:
        warnings.append(f"proposal ledger has {bad} malformed or unsupported mixed-schema row(s)")
    if truncated:
        warnings.append("proposal ledger exceeds read budget; lifecycle counts are partial")
    # A malformed row is not harmless: it makes aggregate counts incomplete.
    return rows, "partial" if truncated or bad else "observed", bad + (1 if truncated else 0)


def _exact_enactment_state(proposal: dict, *, deadline: float) -> tuple[str, str]:
    """Bounded local proof of lifecycle state; never trusts an acceptance or prose."""
    rows = proposal["lifecycle"]
    verdict_index = next((i for i in range(len(rows) - 1, -1, -1)
                          if rows[i].get("verdict")), None)
    if verdict_index is None or rows[verdict_index].get("verdict") not in ("accepted", "auto-accept"):
        return "unknown", ""
    enacted_commit = None
    for row in reversed(rows[verdict_index + 1:]):
        evidence = row.get("enactment")
        if not isinstance(evidence, dict):
            continue
        commit, paths = evidence.get("commit"), evidence.get("paths")
        if (not isinstance(commit, str) or not _FULL_SHA.fullmatch(commit)
                or not isinstance(paths, list) or not paths
                or any(not isinstance(p, str) or not p or p.startswith("/") or ".." in Path(p).parts
                       for p in paths)):
            continue
        changed, error = _run_bounded(["git", "-C", str(ROOT), "diff-tree", "--no-commit-id",
                                       "--name-only", "-r", "--root", commit], deadline=deadline,
                                      env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        if error:
            return "unknown", error
        changed_paths = set((changed or "").splitlines())
        # Exact parity with project_summary.proposal_healing_state: an accepted
        # skill proposal must prove the targeted SKILL.md changed, not merely a
        # README or another listed file.
        required_contract = ps._target_skill_contract(proposal)
        if (not set(paths).issubset(changed_paths)
                or ((proposal["first"].get("target_type") or "").strip() == "skill"
                    and (required_contract is None or required_contract not in paths
                         or required_contract not in changed_paths))):
            continue
        enacted_commit = commit
        break
    if enacted_commit is None:
        return "pending", ""
    for row in reversed(rows[verdict_index + 1:]):
        evidence = row.get("verification")
        if (isinstance(evidence, dict) and evidence.get("commit") == enacted_commit
                and isinstance(evidence.get("command"), str) and evidence["command"].strip()
                and evidence.get("result") == "pass"
                and isinstance(evidence.get("output_sha256"), str)
                and _SHA256.fullmatch(evidence["output_sha256"])):
            return "verified", ""
    return "enacted", ""


def _lifecycle_observation(warnings: list[str], *, deadline: float) -> dict:
    rows, row_status, row_unknown = _proposal_rows_bounded(warnings)
    proposals = ps.collapse_proposals(rows)
    accepted = [p for p in proposals.values()
                if ps.final_verdict(p) in ("accepted", "auto-accept")]
    enacted = verified = 0
    unknown = row_unknown
    for proposal in accepted[:OPS_MAX_LIFECYCLE_PROPOSALS]:
        state, error = _exact_enactment_state(proposal, deadline=deadline)
        if error:
            unknown += 1
            warnings.append(f"lifecycle evidence unavailable: {error}")
        elif state == "enacted":
            enacted += 1
        elif state == "verified":
            enacted += 1
            verified += 1
    if len(accepted) > OPS_MAX_LIFECYCLE_PROPOSALS:
        unknown += len(accepted) - OPS_MAX_LIFECYCLE_PROPOSALS
        warnings.append("lifecycle evidence count capped by proposal budget")
    status = "partial" if row_status == "partial" or unknown else "observed"
    return {"counts": _fact({"accepted": len(accepted), "enacted": enacted,
                               "verified": verified, "unverified_or_pending": len(accepted) - enacted,
                               "evidence_unknown": unknown}, status,
                              "proposal ledger + exact local commit/path checks",
                              "acceptance is a decision only; enactment/verification require exact evidence")}


def _repo_observation(*, deadline: float) -> dict:
    git_env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    head, head_error = _run_bounded(["git", "-C", str(ROOT), "rev-parse", "--short=12", "HEAD"],
                                    deadline=deadline, env=git_env)
    branch, branch_error = _run_bounded(["git", "-C", str(ROOT), "branch", "--show-current"],
                                        deadline=deadline, env=git_env)
    porcelain, dirty_error = _run_bounded(
        ["git", "-C", str(ROOT), "status", "--porcelain=v1", "--untracked-files=no"],
        deadline=deadline, env=git_env)
    if dirty_error:
        dirty = _fact(None, "unknown", "git status --porcelain", dirty_error)
    else:
        dirty = _fact(len((porcelain or "").splitlines()), "observed", "git status --porcelain",
                      "tracked paths only; untracked files, paths, and contents are intentionally omitted")
    return {"head": _fact((head or "").strip() or None, "observed" if not head_error else "unknown",
                           "git rev-parse", head_error or ""),
            "branch": _fact((branch or "").strip() or None, "observed" if not branch_error else "unknown",
                             "git branch --show-current", branch_error or ""),
            "tracked_dirty_count": dirty}


def _operations_unavailable(reason: str) -> dict:
    unknown = _fact(None, "unknown", "operations single-flight", reason)
    return {"schema_version": 1, "generated_at": _now(), "read_only": True,
            "poll": _fact("unavailable", "unknown", "operations single-flight", reason),
            "server": {"alive": _fact(True, "observed", "this successful /api/operations response",
                                       "only this process/request is observed")},
            "watcher": {"state": unknown},
            "pipeline": {"last_success": unknown, "last_failure": unknown},
            "projection": {"generated_at": unknown, "age_seconds": unknown},
            "cursors": {"framework_harvest": unknown, "consumer": unknown},
            "proposals": {"counts": unknown}, "repo": None, "warnings": [reason]}


def _cached_operations(reason: str) -> dict:
    # JSON round-trip creates an independent object; callers cannot mutate the
    # shared cache while another request serves it.
    cached = json.loads(json.dumps(_ops_cache["data"]))
    cached["poll"] = _fact("cached", "stale", "operations short cache", reason)
    cached["warnings"] = list(cached.get("warnings", [])) + [reason]
    return cached


def _build_operations_snapshot(deadline: float) -> dict:
    """Collect one bounded observation pass.  Caller holds _OPS_LOCK."""
    warnings: list[str] = []
    return {"schema_version": 1, "generated_at": _now(), "read_only": True,
            "poll": _fact("fresh", "observed", "operations single-flight",
                          f"shared wall-clock budget {OPS_TOTAL_BUDGET_S}s"),
            "server": {"alive": _fact(True, "observed", "this successful /api/operations response",
                                       "only this process/request is observed")},
            "watcher": _watcher_observation(warnings),
            "pipeline": _pipeline_observation(warnings),
            "projection": _projection_observation(warnings),
            "cursors": _cursor_observation(warnings, deadline=deadline),
            "proposals": _lifecycle_observation(warnings, deadline=deadline),
            "repo": _repo_observation(deadline=deadline), "warnings": warnings}


def operations_snapshot() -> dict:
    """Return a cached/single-flight bounded observation pass; never writes state."""
    now = time.monotonic()
    if (_ops_cache["data"] is not None
            and now - _ops_cache["mono"] < OPS_CACHE_TTL_S):
        return _cached_operations("served from short cache; no new subprocesses started")
    if not _OPS_LOCK.acquire(blocking=False):
        if _ops_cache["data"] is not None:
            return _cached_operations("another operations poll is in progress")
        return _operations_unavailable("another operations poll is in progress; no cache exists")
    try:
        now = time.monotonic()
        if (_ops_cache["data"] is not None
                and now - _ops_cache["mono"] < OPS_CACHE_TTL_S):
            return _cached_operations("served from short cache after single-flight wait")
        data = _build_operations_snapshot(now + OPS_TOTAL_BUDGET_S)
        _ops_cache["data"], _ops_cache["mono"] = data, time.monotonic()
        return data
    finally:
        _OPS_LOCK.release()


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(VIEW), **k)

    def log_message(self, *a):  # quieter
        pass

    def _send(self, code: int, obj: dict):
        """Write a JSON response. A client that hangs up mid-write raises a
        broken-pipe/connection error; swallow it so it cannot crash the request
        thread (the response is already lost — there is nothing useful to do)."""
        payload = json.dumps(obj).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionError):
            pass

    def _pid_from(self, parts: list[str]) -> str | None:
        if len(parts) >= 3 and PID_RE.match(parts[2]):
            return parts[2]
        return None

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        # Non-API paths fall through to SimpleHTTPRequestHandler, which serves
        # ONLY out of `directory=VIEW`: translate_path() normalizes the URL and
        # strips any "..", so the static handler cannot traverse outside VIEW.
        if not self.path.startswith("/api/"):
            return super().do_GET()
        parts = self.path.strip("/").split("/")  # ['api', ...]
        try:
            if self.path == "/api/summary":
                # Live dashboard data — computed from the ledgers now, not baked.
                return self._send(200, current_summary())
            if self.path == "/api/map":
                # Live cluster-map data — computed from the ledgers now, not baked.
                return self._send(200, current_map())
            if self.path == "/api/operations":
                # Read-only, bounded local observations.  Unlike /api/summary,
                # this intentionally does not rebuild projections or touch ledgers.
                return self._send(200, operations_snapshot())
            if self.path == "/api/proposals":
                return self._send(200, {"proposals": open_framework_proposals()})
            pid = self._pid_from(parts)  # validated against ^P-\d+$ before any fs/argv use
            if pid:
                first = proposal_first(pid)
                if not first:
                    return self._send(404, {"error": "unknown proposal"})
                # Deterministic: read the stored card; only draft (one LLM call) if
                # none exists yet. generate_card persists it exactly once.
                card = stored_card(pid) or generate_card(first)
                amended = latest_amended_draft(pid)
                return self._send(200, {"proposal": first, "card": card,
                                        "discussion": discussion(pid),
                                        "amended_draft": amended.get("change") if amended else None})
            return self._send(404, {"error": "no route"})
        except GemmaError as e:
            return self._send(503, {"error": str(e)})
        except Exception:  # noqa: BLE001 — never leak a stack/internal to the client
            print(f"do_GET: unhandled error on {self.path}", file=sys.stderr)
            return self._send(500, {"error": "internal error"})

    def do_POST(self):
        parts = self.path.strip("/").split("/")  # ['api','proposal','P-NNN','action']
        pid = self._pid_from(parts)  # validated against ^P-\d+$ before any fs/argv use
        action = parts[3] if len(parts) >= 4 else ""
        if not pid:
            return self._send(404, {"error": "bad proposal id"})
        first = proposal_first(pid)
        if not first:
            return self._send(404, {"error": "unknown proposal"})
        body = self._body()
        try:
            if action == "discuss":
                msg = (body.get("message") or "").strip()
                if not msg:
                    return self._send(400, {"error": "empty message"})
                return self._send(200, {"reply": discuss_turn(first, msg),
                                        "discussion": discussion(pid)})
            if action == "synthesize":
                # Fold the discussion into a crisp amended proposal; persist it.
                return self._send(200, {"amended_change": synthesize_amended(first)})
            if action == "verdict":
                v, note = body.get("verdict", ""), (body.get("note") or "").strip()
                basis = body.get("basis") or "original"
                actor_id = body.get("actor_id")
                # Reason optional for accept (closed steward assertion); required to reject.
                if v != "accept" and not note:
                    return self._send(400, {"error": "a reason is required to reject"})
                if basis not in ("original", "amended"):
                    return self._send(400, {"error": "bad basis"})
                try:
                    actor_record(actor_id)
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                accepted_body = None
                # The final reviewer-edited text is passed directly to the governed
                # CLI. Ignored card drafts may aid discussion but never supply the
                # accepted/recoverable body.
                if v == "accept" and basis == "amended":
                    amended_change = body.get("amended_change")
                    if not isinstance(amended_change, str) or not amended_change.strip():
                        return self._send(400, {"error": "amended_change required for amended basis"})
                    accepted_body = amended_change
                out = record_verdict(pid, v, note, basis, actor_id, accepted_body)
                # A verdict on an already-decided proposal (CLI exit 4) or a bad
                # verdict is a clean client error, not a 500. 409 = conflict with
                # the proposal's recorded state; 400 = malformed verdict.
                if not out.get("ok"):
                    code = 409 if out.get("exit_code") == 4 else 400
                    return self._send(code, out)
                out["basis"] = basis
                # On ACCEPT, auto-write the implementation handoff so the steward's
                # decision and the dev brief are a single step. If the file write
                # fails, the accepted proposal body remains durable and POST
                # /handoff can reconstruct that verified body for a new handoff.
                if v == "accept":
                    try:
                        out["handoff_path"] = write_handoff(first, basis, actor_id)
                    except Exception:  # noqa: BLE001 — accepted row is already durable
                        out["handoff_status"] = "pending"
                        out["handoff_recovery"] = "retry POST /api/proposal/<id>/handoff"
                        _schedule_refresh()
                        return self._send(202, out)
                # Any successful verdict changes the open set — refresh the static
                # projection so the dashboard inbox/loop match the live queue.
                _schedule_refresh()
                return self._send(200, out)
            if action == "handoff":
                basis = body.get("basis") or "original"
                actor_id = body.get("actor_id")
                if basis not in ("original", "amended"):
                    return self._send(400, {"error": "bad basis"})
                try:
                    actor_record(actor_id)
                except ValueError as e:
                    return self._send(400, {"error": str(e)})
                try:
                    path = write_handoff(first, basis, actor_id)
                except ValueError as e:
                    return self._send(409, {"error": str(e)})
                return self._send(200, {"path": path})
            return self._send(404, {"error": "no action"})
        except GemmaError as e:
            return self._send(503, {"error": str(e)})
        except Exception:  # noqa: BLE001 — never leak a stack/internal to the client
            print(f"do_POST: unhandled error on {self.path}", file=sys.stderr)
            return self._send(500, {"error": "internal error"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5180)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"brain_server: http://{a.host}:{a.port}  (view={VIEW}, model={MODEL})")
    srv.serve_forever()


if __name__ == "__main__":
    main()
