#!/usr/bin/env python3
"""Dynamic brain backend — serves the static view dir AND a small JSON API that
makes proposal review conversational and frictionless.

Smallest-slice scope (S25): one focused proposal-review loop —
  GET  /api/proposals                 list open framework proposals
  GET  /api/proposal/<id>             proposal + card + discussion + amended_draft
  POST /api/proposal/<id>/discuss     {message}  -> Gemma turn (amend dialogue)
  POST /api/proposal/<id>/synthesize  -> Gemma turns the discussion into a crisp
                                         amended proposal 'change'; persists it
  POST /api/proposal/<id>/verdict     {verdict,note,basis,amended_change?} -> exec
                                         blessed CLI; on accept auto-writes handoff
  POST /api/proposal/<id>/handoff     -> write handoffs/<id>.md (manual regen)

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
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEW = ROOT / "memory" / "brain" / "view"
PROPOSALS = ROOT / "memory" / "brain" / "proposals.jsonl"
CARDS = ROOT / "memory" / "brain" / "proposal_cards.jsonl"
FEEDBACK = ROOT / "memory" / "feedback.jsonl"
RULES = ROOT / "memory" / "brain" / "rules.md"
SKILLS = ROOT / ".agents" / "skills"
HANDOFFS = ROOT / "handoffs"
CLI = ROOT / "scripts" / "review_proposal_cli.py"

GEMMA_URL = "http://127.0.0.1:8000/v1/chat/completions"
MODEL = "gemma-4-26b-a4b"
PID_RE = re.compile(r"^P-\d+$")

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
        "You help a human review proposals to improve the agent_system framework "
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
        "You help a human refine a proposal to improve the agent_system framework. "
        "The human may say none of the options look clean, or raise a worry. Engage "
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


def write_handoff(first: dict, basis: str = "original") -> str:
    pid = first.get("proposal_id")
    card = stored_card(pid) or generate_card(first)
    disc = discussion(pid)
    disc_txt = "\n".join(f"**{t['role']}:** {t['content']}" for t in disc) or "_(no discussion)_"
    # Choose the governed proposal body: the amended draft (final, possibly
    # human-edited) when accepting on that basis, else the original verbatim.
    amended = latest_amended_draft(pid) if basis == "amended" else None
    if amended:
        body_label = "Amended proposal (final form)"
        body_text = amended.get("change", "")
    else:
        body_label = "Original proposal (verbatim)"
        body_text = first.get("change", "")
    synth = ""
    try:
        synth = gemma([
            {"role": "system", "content":
                "Synthesize a concrete implementation brief for a dev agent from this "
                "proposal and its discussion: the agreed change, the files likely to "
                "touch, and 2-4 acceptance criteria. Markdown, no preamble."},
            {"role": "user", "content":
                f"PROPOSAL {pid}: {first.get('title')}\nchange: {body_text}\n"
                f"reasoning: {first.get('reasoning')}\n\nDISCUSSION:\n{disc_txt}"}
        ], max_tokens=700, temperature=0.2)
    except Exception as e:  # noqa: BLE001
        synth = f"_(synthesis unavailable: {e})_"
    HANDOFFS.mkdir(exist_ok=True)
    md = (
        f"# Implementation handoff — {pid}\n\n"
        f"_Generated {_now()} by the brain proposal-review loop (basis: {basis}). "
        f"Pass to a dev agent._\n\n"
        f"- **Target:** `{first.get('target_type')}:{first.get('target')}`\n"
        f"- **Title:** {first.get('title')}\n\n"
        f"## {body_label}\n\n{body_text}\n\n"
        f"### Why\n\n{first.get('reasoning')}\n\n"
        f"## What it means\n\n{card.get('means','')}\n\n"
        f"## Discussion\n\n{disc_txt}\n\n"
        f"## Agreed change & implementation brief\n\n{synth}\n"
    )
    path = HANDOFFS / f"{pid}.md"
    path.write_text(md)
    return str(path.relative_to(ROOT))


def record_verdict(pid: str, verdict: str, note: str, basis: str = "original") -> dict:
    if verdict not in ("accept", "reject", "needs_revision"):
        return {"ok": False, "error": "bad verdict"}
    if basis not in ("original", "amended"):
        return {"ok": False, "error": "bad basis"}
    proc = subprocess.run(
        [sys.executable, str(CLI), "--proposal-id", pid, "--verdict", verdict,
         "--note", note, "--basis", basis, "--agent", "human:ui"],
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
                # Reason optional for accept (human authority); required to reject.
                if v != "accept" and not note:
                    return self._send(400, {"error": "a reason is required to reject"})
                if basis not in ("original", "amended"):
                    return self._send(400, {"error": "bad basis"})
                # If accepting the amended draft, persist the (possibly human-EDITED)
                # text as a fresh amended_draft BEFORE recording, so the governed
                # and handoff form is the final edited text.
                if basis == "amended":
                    amended_change = (body.get("amended_change") or "").strip()
                    if not amended_change:
                        return self._send(400, {"error": "amended_change required for amended basis"})
                    append_amended_draft(pid, amended_change)
                out = record_verdict(pid, v, note, basis)
                # A verdict on an already-decided proposal (CLI exit 4) or a bad
                # verdict is a clean client error, not a 500. 409 = conflict with
                # the proposal's recorded state; 400 = malformed verdict.
                if not out.get("ok"):
                    code = 409 if out.get("exit_code") == 4 else 400
                    return self._send(code, out)
                out["basis"] = basis
                # On ACCEPT, auto-write the implementation handoff so the human's
                # decision and the dev brief are a single step.
                if v == "accept":
                    out["handoff_path"] = write_handoff(first, basis)
                # Any successful verdict changes the open set — refresh the static
                # projection so the dashboard inbox/loop match the live queue.
                _schedule_refresh()
                return self._send(200, out)
            if action == "handoff":
                basis = body.get("basis") or "original"
                if basis not in ("original", "amended"):
                    return self._send(400, {"error": "bad basis"})
                return self._send(200, {"path": write_handoff(first, basis)})
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
