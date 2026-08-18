#!/usr/bin/env python3
"""Tests for scripts/brain_server.py — the dynamic proposal-review backend.

These exercise the module's PURE functions (no HTTP server, no real LLM):
  - open_framework_proposals  — scope filter excludes research/a_bgt_rsi targets
  - generate_card             — persists ONE card; a re-GET reads it back with no
                                second gemma call (the file is canonical)
  - discuss_turn              — appends user + assistant turns to the cards ledger
  - write_handoff             — writes handoffs/<id>.md

Design invariant under test: Gemma is only a drafting assistant; every output is
written through to the append-only ledger, and projection/re-reads never call the
model. We assert this by counting calls on a deterministic gemma STUB.

The module pins its paths at import time as module-level constants
(brain_server.PROPOSALS, .CARDS, .FEEDBACK, .RULES, .SKILLS, .HANDOFFS, .ROOT).
We monkeypatch all of them at a tmp fixture dir so the real brain is untouched.
write_handoff returns `path.relative_to(ROOT)`, so ROOT is repointed at tmp too.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
REAL_LEDGER_HELPER = REPO / "scripts" / "brain_ledger.py"
sys.path.insert(0, str(REPO / "scripts"))

import brain_server as bs  # noqa: E402

REAL_CLI = REPO / "scripts" / "review_proposal_cli.py"


# A framework proposal (target is a skill) and a research one (target names the
# a_bgt_rsi consumer apparatus) — proposal_scope() should exclude the latter.
FW_PROP = {
    "timestamp": "2026-06-01T00:00:00Z", "proposal_id": "P-100",
    "agent_id": "claude-code-main", "title": "Tighten the validate skill",
    "target_type": "skill", "target": "validate",
    "change": "make near-misses always fail", "reasoning": "no coercion",
    "status": "open",
}
RESEARCH_PROP = {
    "timestamp": "2026-06-01T00:01:00Z", "proposal_id": "P-200",
    "agent_id": "nara", "title": "Refactor the apparatus loop",
    "target_type": "file", "target": "a_bgt_rsi/orchestrator/loop.py",
    "change": "split the loop", "reasoning": "too long",
    "status": "open",
}
RESEARCH_PROP_EXPLICIT = {
    "timestamp": "2026-06-01T00:02:00Z", "proposal_id": "P-300",
    "agent_id": "nara", "title": "Explicitly research-scoped",
    "target_type": "skill", "target": "validate", "scope": "research",
    "change": "x", "reasoning": "y", "status": "open",
}


class GemmaStub:
    """Deterministic stand-in for brain_server.gemma. Records call count and the
    last messages so tests can assert no-LLM-on-reread and turn ordering."""

    def __init__(self, reply=None):
        self.calls = 0
        self.last_messages = None
        # Default reply is strict card JSON so generate_card's json.loads path
        # (not its parse-fallback) is what we exercise.
        self._reply = reply or json.dumps({
            "means": "It makes validate fail on near-misses.",
            "pros_accept": ["honest checks"], "cons_accept": ["more red runs"],
            "pros_reject": ["less churn"], "cons_reject": ["hides drift"],
            "rule_check": {"conflict": False, "rule": None, "why": "consistent"},
        })

    def __call__(self, messages, max_tokens=700, temperature=0.3):
        self.calls += 1
        self.last_messages = messages
        return self._reply


@pytest.fixture
def brain(tmp_path, monkeypatch):
    """A self-contained tmp brain: monkeypatch every path constant + gemma.

    Yields a namespace with the fixture dir, the gemma stub, and a seed() helper
    that writes proposals into the temp ledger.
    """
    root = tmp_path
    brain_dir = root / "memory" / "brain"
    brain_dir.mkdir(parents=True)
    skills = root / ".agents" / "skills"
    skills.mkdir(parents=True)
    (skills / "validate").mkdir()
    (skills / "validate" / "SKILL.md").write_text(
        "---\nlayer: A\n---\n# validate\nRun checks as independent pass/fail.\n")
    handoffs = root / "handoffs"

    proposals = brain_dir / "proposals.jsonl"
    cards = brain_dir / "proposal_cards.jsonl"
    feedback = root / "memory" / "feedback.jsonl"
    rules = brain_dir / "rules.md"
    proposals.write_text("")
    cards.write_text("")
    feedback.write_text("")
    rules.write_text("# Active rules\n\n- FR-001 never coerce a near-miss.\n")

    # A copy of the blessed verdict CLI inside the tmp ROOT so that when
    # record_verdict() execs it, the CLI derives its OWN PROPOSALS path from its
    # location (ROOT.parent.parent) and lands on the temp ledger — never the real
    # one. Mirrors the subprocess-with-copied-CLI pattern in the CLI test suite.
    fake_scripts = root / "scripts"
    fake_scripts.mkdir()
    fake_cli = fake_scripts / "review_proposal_cli.py"
    shutil.copy(REAL_CLI, fake_cli)
    shutil.copy(REAL_LEDGER_HELPER, fake_scripts / "brain_ledger.py")

    stub = GemmaStub()
    # Repoint ROOT so write_handoff's relative_to(ROOT) resolves inside tmp.
    monkeypatch.setattr(bs, "ROOT", root)
    monkeypatch.setattr(bs, "PROPOSALS", proposals)
    monkeypatch.setattr(bs, "CARDS", cards)
    monkeypatch.setattr(bs, "FEEDBACK", feedback)
    monkeypatch.setattr(bs, "RULES", rules)
    monkeypatch.setattr(bs, "SKILLS", skills)
    monkeypatch.setattr(bs, "HANDOFFS", handoffs)
    monkeypatch.setattr(bs, "CLI", fake_cli)
    monkeypatch.setattr(bs, "gemma", stub)
    # The verdict route schedules a background projection refresh; stub the
    # scheduler so route tests neither spawn threads nor exec projector
    # subprocesses. refresh_projection itself is exercised directly below.
    monkeypatch.setattr(bs, "_schedule_refresh", lambda: None)
    # Start each test with empty live caches so a stubbed build_summary/build_map is
    # actually invoked (the TTL cache would otherwise serve a prior test's data).
    bs._summary_cache["data"] = None
    bs._summary_cache["mono"] = 0.0
    bs._map_cache["data"] = None
    bs._map_cache["mono"] = 0.0

    class Brain:
        def __init__(self):
            self.root = root
            self.proposals = proposals
            self.cards = cards
            self.handoffs = handoffs
            self.gemma = stub

        def seed(self, *rows):
            proposals.write_text("".join(json.dumps(r) + "\n" for r in rows))

        def card_lines(self):
            return [json.loads(l) for l in cards.read_text().splitlines()
                    if l.strip()]

        def amended_lines(self):
            return [r for r in self.card_lines()
                    if r.get("kind") == "amended_draft"]

    return Brain()


# ---------------------------------------------------------------------------
# open_framework_proposals — scope filter
# ---------------------------------------------------------------------------

def test_open_framework_proposals_excludes_research_targets(brain):
    brain.seed(FW_PROP, RESEARCH_PROP, RESEARCH_PROP_EXPLICIT)
    out = bs.open_framework_proposals()
    ids = [p["proposal_id"] for p in out]
    assert ids == ["P-100"]  # research (path-named) and explicit-scope excluded
    row = out[0]
    assert row["title"] == "Tighten the validate skill"
    assert row["target"] == "validate"
    assert row["target_type"] == "skill"
    assert row["verdict"] == "open"


def test_open_framework_proposals_excludes_decided(brain):
    """A proposal whose latest verdict is closed (accepted/rejected) drops out;
    open and human-review stay."""
    decided = dict(FW_PROP, proposal_id="P-100")
    verdict = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-100",
               "agent_id": "human:ui", "verdict": "accepted", "status": "closed"}
    human_review = dict(FW_PROP, proposal_id="P-101", title="Still open for review")
    hr_verdict = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-101",
                  "agent_id": "human:ui", "verdict": "human-review",
                  "status": "human-review"}
    brain.seed(decided, verdict, human_review, hr_verdict)
    ids = [p["proposal_id"] for p in bs.open_framework_proposals()]
    assert ids == ["P-101"]


# ---------------------------------------------------------------------------
# generate_card — persists one card; reread does not call gemma again
# ---------------------------------------------------------------------------

def test_generate_card_persists_one_card_and_parses_json(brain):
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    card = bs.generate_card(first)

    assert brain.gemma.calls == 1
    assert card["kind"] == "card"
    assert card["proposal_id"] == "P-100"
    assert card["means"] == "It makes validate fail on near-misses."
    assert card["pros_accept"] == ["honest checks"]
    assert card["rule_check"] == {"conflict": False, "rule": None,
                                  "why": "consistent"}

    lines = brain.card_lines()
    assert len(lines) == 1  # exactly one card persisted
    assert lines[0]["proposal_id"] == "P-100"
    assert lines[0]["kind"] == "card"


def test_stored_card_reads_without_a_second_gemma_call(brain):
    """The file is canonical: once a card exists, stored_card() serves it and the
    model is NOT consulted again (the simulated re-GET path)."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.generate_card(first)
    assert brain.gemma.calls == 1

    # Simulate the do_GET branch: `stored_card(pid) or generate_card(first)`.
    cached = bs.stored_card("P-100") or bs.generate_card(first)
    assert cached["means"] == "It makes validate fail on near-misses."
    assert brain.gemma.calls == 1  # no second call
    assert len(brain.card_lines()) == 1  # no duplicate card appended


def test_generate_card_parse_fallback_on_bad_json(brain):
    """Non-JSON model output falls back to a means-only card (still persisted),
    without raising."""
    brain.gemma._reply = "this is not json at all"
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    card = bs.generate_card(first)
    assert card["means"].startswith("this is not json")
    assert card["rule_check"]["why"] == "parse-fallback"
    assert len(brain.card_lines()) == 1


# ---------------------------------------------------------------------------
# discuss_turn — appends user + assistant
# ---------------------------------------------------------------------------

def test_discuss_turn_appends_user_then_assistant(brain):
    brain.gemma._reply = "Here is a sharper amended change."
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")

    reply = bs.discuss_turn(first, "None of these options look clean.")
    assert reply == "Here is a sharper amended change."
    assert brain.gemma.calls == 1

    disc = bs.discussion("P-100")
    assert [t["role"] for t in disc] == ["user", "assistant"]
    assert disc[0]["content"] == "None of these options look clean."
    assert disc[1]["content"] == "Here is a sharper amended change."
    assert all(t["ts"] for t in disc)

    # the cards ledger now holds exactly the two discuss rows
    kinds = [r["kind"] for r in brain.card_lines()]
    assert kinds == ["discuss", "discuss"]


def test_discuss_turn_carries_prior_history_into_prompt(brain):
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.discuss_turn(first, "first message")
    bs.discuss_turn(first, "second message")

    # Four rows: u/a/u/a — prior turns persisted between calls.
    assert len(bs.discussion("P-100")) == 4
    # The 2nd call's prompt includes the prior user+assistant turns plus the new
    # user message (system + seed-user + 2 history + 1 new = 5 messages).
    msgs = brain.gemma.last_messages
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["content"] == "second message"
    assert any(m["content"] == "first message" for m in msgs)


# ---------------------------------------------------------------------------
# write_handoff — writes handoffs/<id>.md
# ---------------------------------------------------------------------------

def test_write_handoff_writes_markdown_file(brain):
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.discuss_turn(first, "Let us narrow scope.")

    rel = bs.write_handoff(first)
    assert rel == "handoffs/P-100.md"
    md_path = brain.handoffs / "P-100.md"
    assert md_path.exists()

    text = md_path.read_text()
    assert "# Implementation handoff — P-100" in text
    assert "Tighten the validate skill" in text          # title
    assert "make near-misses always fail" in text        # original change
    assert "Let us narrow scope." in text                # discussion echoed
    assert "## Agreed change & implementation brief" in text


def test_write_handoff_reuses_existing_card(brain):
    """If a card already exists, write_handoff must not regenerate it (it reuses
    stored_card); only the synthesis brief calls gemma."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.generate_card(first)
    calls_after_card = brain.gemma.calls  # == 1

    bs.write_handoff(first)
    # exactly one more gemma call (the synthesis), not two (card + synth)
    assert brain.gemma.calls == calls_after_card + 1
    assert len(brain.card_lines()) == 1  # no second card row


# ---------------------------------------------------------------------------
# synthesize_amended / latest_amended_draft — the amended_draft card kind (§1,§2)
# ---------------------------------------------------------------------------

def test_synthesize_amended_appends_one_amended_draft_and_returns_text(brain):
    """synthesize_amended turns original change + discussion into a crisp amended
    proposal text via Gemma, persists exactly ONE amended_draft row, and returns
    that text. The persisted entry carries the contract's kind/proposal_id/model."""
    brain.gemma._reply = "Make validate raise on any near-miss with a logged reason."
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.discuss_turn(first, "near-misses should never pass silently")
    calls_before = brain.gemma.calls

    text = bs.synthesize_amended(first)
    assert text == "Make validate raise on any near-miss with a logged reason."
    assert brain.gemma.calls == calls_before + 1  # exactly one synthesis call

    amended = brain.amended_lines()
    assert len(amended) == 1
    row = amended[0]
    assert row["kind"] == "amended_draft"
    assert row["proposal_id"] == "P-100"
    assert row["change"] == "Make validate raise on any near-miss with a logged reason."
    assert row["model"] == bs.MODEL
    assert row["generated_at"]


def test_latest_amended_draft_returns_newest_change(brain):
    """Append-only: re-synthesizing appends a SECOND amended_draft and the latest
    one wins; latest_amended_draft returns the newest entry (or None if absent)."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    assert bs.latest_amended_draft("P-100") is None  # none yet

    brain.gemma._reply = "first amended form"
    bs.synthesize_amended(first)
    brain.gemma._reply = "second, sharper amended form"
    bs.synthesize_amended(first)

    assert len(brain.amended_lines()) == 2  # append-only, no edit-in-place
    latest = bs.latest_amended_draft("P-100")
    assert latest["change"] == "second, sharper amended form"


# ---------------------------------------------------------------------------
# write_handoff(basis=...) — amended body when basis='amended' (§2)
# ---------------------------------------------------------------------------

def _handoff_body(text: str) -> str:
    """Extract the labelled proposal-body section of a handoff (between the body
    heading and the following '### Why' section) so a test can assert what the
    GOVERNED body is, independent of discussion/synthesis echoes elsewhere."""
    marker = "## "
    for header in ("## Amended proposal (final form)",
                   "## Original proposal (verbatim)"):
        if header in text:
            after = text.split(header, 1)[1]
            return after.split("### Why", 1)[0]
    return ""


def test_write_handoff_amended_uses_amended_draft_body(brain):
    """With basis='amended' and an amended_draft present, the handoff body is the
    amended text (labelled final form), NOT the original verbatim change."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.generate_card(first)  # card from the default JSON stub, before we swap _reply
    brain.gemma._reply = "Validate now fails closed on every near-miss."
    bs.synthesize_amended(first)

    rel = bs.write_handoff(first, basis="amended")
    text = (brain.handoffs / "P-100.md").read_text()
    assert rel == "handoffs/P-100.md"
    assert "Amended proposal (final form)" in text  # labelled final form
    body = _handoff_body(text)
    assert "Validate now fails closed on every near-miss." in body  # amended body
    assert "make near-misses always fail" not in body              # not original


def test_write_handoff_amended_falls_back_to_original_without_draft(brain):
    """basis='amended' but NO amended_draft exists -> handoff uses the original
    verbatim change (graceful fallback, never an empty body)."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.write_handoff(first, basis="amended")
    text = (brain.handoffs / "P-100.md").read_text()
    assert "make near-misses always fail" in _handoff_body(text)  # original body


def test_write_handoff_default_basis_is_original(brain):
    """Default basis is 'original': the GOVERNED body is the original verbatim
    change even when an amended_draft happens to exist."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    bs.generate_card(first)  # card from the default JSON stub, before we swap _reply
    brain.gemma._reply = "the amended text that should NOT be the body"
    bs.synthesize_amended(first)

    bs.write_handoff(first)  # no basis arg -> original
    text = (brain.handoffs / "P-100.md").read_text()
    body = _handoff_body(text)
    assert "make near-misses always fail" in body  # original is the governed body
    assert "the amended text that should NOT be the body" not in body


# ---------------------------------------------------------------------------
# GET payload — /api/proposal/<id> also returns amended_draft (§2)
# ---------------------------------------------------------------------------

def test_proposal_payload_includes_amended_draft(brain):
    """The proposal detail must surface the latest amended_draft change (or null)
    so the UI can enable the 'accept amended' path. We assert the helper the GET
    route reads — latest_amended_draft — and the card it pairs it with."""
    brain.seed(FW_PROP)
    first = bs.proposal_first("P-100")
    # before synthesis: no amended draft
    assert bs.latest_amended_draft("P-100") is None
    # after synthesis: the change string is available for the payload
    brain.gemma._reply = "the crisp amended change"
    bs.synthesize_amended(first)
    latest = bs.latest_amended_draft("P-100")
    assert latest is not None and latest["change"] == "the crisp amended change"


# ---------------------------------------------------------------------------
# record_verdict basis threading -> blessed CLI (§2,§3)
# ---------------------------------------------------------------------------

def test_record_verdict_threads_closed_actor_to_cli(brain):
    """record_verdict threads its closed actor into the CLI with basis 'original'; the
    blessed CLI appends an outcome carrying basis='original'. (Real ledger is the
    tmp copy via the monkeypatched bs.CLI / bs.PROPOSALS.)"""
    brain.seed(FW_PROP)
    out = bs.record_verdict("P-100", "accept", "ship original", actor_id="derrick")
    assert out.get("ok") is True
    rows = [json.loads(l) for l in brain.proposals.read_text().splitlines()
            if l.strip()]
    outcome = rows[-1]
    assert outcome["verdict"] == "accepted"
    assert outcome["basis"] == "original"
    assert outcome["agent_id"] == "derrick"
    assert outcome["actor"] == {
        "id": "derrick", "type": "human", "authentication": "ui-asserted",
        "cryptographically_authenticated": False,
    }


def test_record_verdict_basis_amended_threads_to_cli(brain):
    """record_verdict(..., basis='amended') threads --basis amended to the CLI,
    and the appended outcome records basis='amended'."""
    brain.seed(FW_PROP)
    out = bs.record_verdict("P-100", "accept", "ship amended", basis="amended",
                            actor_id="oracle")
    assert out.get("ok") is True
    rows = [json.loads(l) for l in brain.proposals.read_text().splitlines()
            if l.strip()]
    outcome = rows[-1]
    assert outcome["verdict"] == "accepted"
    assert outcome["basis"] == "amended"
    assert outcome["actor"]["id"] == "oracle"


@pytest.mark.parametrize("actor_id", [None, "mallory", "human:ui"])
def test_record_verdict_rejects_missing_or_arbitrary_actor_without_write(brain, actor_id):
    brain.seed(FW_PROP)
    out = bs.record_verdict("P-100", "accept", "x", actor_id=actor_id)
    assert out == {"ok": False, "error": "actor_id must be one of: derrick, oracle"}
    assert len(brain.proposals.read_text().splitlines()) == 1


# ---------------------------------------------------------------------------
# verdict ROUTE (in-process, no listening server) — accept auto-writes handoff
# and basis='amended' persists the EDITED text before recording (§2,§4)
# ---------------------------------------------------------------------------

def _post(pid: str, action: str, body: dict):
    """Drive Handler.do_POST in-process with a fake request — no socket, no
    listening server (honors the 'no long-running servers' constraint). Returns
    (status_code, response_obj) by capturing _send."""
    import io

    h = bs.Handler.__new__(bs.Handler)  # bypass __init__ (which wants a socket)
    raw = json.dumps(body).encode()
    h.path = f"/api/proposal/{pid}/{action}"
    h.headers = {"Content-Length": str(len(raw))}
    h.rfile = io.BytesIO(raw)
    captured = {}

    def _send(code, obj):
        captured["code"] = code
        captured["obj"] = obj
    h._send = _send
    h.do_POST()
    return captured["code"], captured["obj"]


def _get(path: str):
    """Drive Handler.do_GET in-process for an /api/* path (no socket). Only safe
    for API routes — non-API paths fall through to the static file handler which
    needs a real socket. Returns (status_code, response_obj) via captured _send."""
    h = bs.Handler.__new__(bs.Handler)
    h.path = path
    h.headers = {}
    captured = {}

    def _send(code, obj):
        captured["code"] = code
        captured["obj"] = obj
    h._send = _send
    h.do_GET()
    return captured["code"], captured["obj"]


# ---------------------------------------------------------------------------
# GET /api/summary — live dashboard data (computed, not baked)
# ---------------------------------------------------------------------------

def test_summary_route_returns_live_built_summary(brain, monkeypatch):
    """GET /api/summary returns the freshly built summary (computed in-process via
    project_summary.build_summary) so the dashboard reads live data, not the baked
    summary_data.js. build_summary is stubbed to keep the test hermetic."""
    monkeypatch.setattr(bs.ps, "build_summary",
                        lambda: {"status_strip": {"system": "ok"}, "marker": "live"})
    code, obj = _get("/api/summary")
    assert code == 200
    assert obj["marker"] == "live"
    assert obj["status_strip"]["system"] == "ok"


def test_current_summary_caches_within_ttl(brain, monkeypatch):
    """Two rapid calls share ONE build (TTL coalescing) and return the same cached
    object by reference — so a 30s-poll fleet of tabs cannot stampede the builder."""
    n = {"c": 0}

    def fake_build():
        n["c"] += 1
        return {"status_strip": {}, "n": n["c"]}

    monkeypatch.setattr(bs.ps, "build_summary", fake_build)
    a = bs.current_summary()
    b = bs.current_summary()
    assert n["c"] == 1   # second served from cache, not rebuilt
    assert a is b        # same object


def test_current_summary_rebuilds_after_ttl(brain, monkeypatch):
    """Once the TTL elapses, the next call rebuilds. We advance a fake monotonic
    clock past _SUMMARY_TTL_S rather than sleeping."""
    n = {"c": 0}

    def fake_build():
        n["c"] += 1
        return {"status_strip": {}, "n": n["c"]}

    clock = {"t": 1000.0}
    monkeypatch.setattr(bs.ps, "build_summary", fake_build)
    monkeypatch.setattr(bs.time, "monotonic", lambda: clock["t"])
    bs.current_summary()                 # build #1 at t=1000
    clock["t"] += bs._SUMMARY_TTL_S + 1  # past the TTL
    bs.current_summary()                 # build #2
    assert n["c"] == 2


# ---------------------------------------------------------------------------
# GET /api/map — live cluster-map data (computed, not baked)
# ---------------------------------------------------------------------------

def test_map_route_returns_live_built_map(brain, monkeypatch):
    """GET /api/map returns the freshly built map (computed in-process via
    project_map.build_map) so the cluster map reads live data, not map_data.js."""
    monkeypatch.setattr(bs.pm, "build_map",
                        lambda: {"generated_at": "x", "nodes": [{"id": "skill:validate"}],
                                 "edges": [], "cards": {}})
    code, obj = _get("/api/map")
    assert code == 200
    assert isinstance(obj["nodes"], list) and obj["nodes"][0]["id"] == "skill:validate"


def test_current_map_caches_within_ttl(brain, monkeypatch):
    """Two rapid calls share ONE build_map (TTL coalescing), same object by ref."""
    n = {"c": 0}

    def fake_build():
        n["c"] += 1
        return {"nodes": [], "edges": [], "cards": {}, "n": n["c"]}

    monkeypatch.setattr(bs.pm, "build_map", fake_build)
    a = bs.current_map()
    b = bs.current_map()
    assert n["c"] == 1
    assert a is b


def test_map_route_build_failure_is_clean_500(brain, monkeypatch):
    """A raising build_map must surface as a clean 500 (caught by do_GET), not an
    unhandled crash — so the client falls back to the baked map_data.js."""
    def boom():
        raise RuntimeError("projector blew up")

    monkeypatch.setattr(bs.pm, "build_map", boom)
    code, obj = _get("/api/map")
    assert code == 500
    assert "error" in obj


def test_summary_route_build_failure_is_clean_500(brain, monkeypatch):
    """Same contract for /api/summary: a raising build_summary -> clean 500."""
    def boom():
        raise RuntimeError("projector blew up")

    monkeypatch.setattr(bs.ps, "build_summary", boom)
    code, obj = _get("/api/summary")
    assert code == 500
    assert "error" in obj


def test_verdict_route_accept_original_returns_handoff_path(brain):
    """Accepting on the ORIGINAL basis records the verdict AND auto-writes the
    handoff — one step. The route returns ok/recorded/basis/handoff_path."""
    brain.seed(FW_PROP)
    code, obj = _post("P-100", "verdict",
                      {"verdict": "accept", "note": "ship it", "basis": "original",
                       "actor_id": "derrick"})
    assert code == 200
    assert obj["ok"] is True and obj["recorded"] == "accepted"
    assert obj["basis"] == "original"
    assert obj["actor"]["id"] == "derrick"
    assert obj["handoff_path"] == "handoffs/P-100.md"
    assert (brain.handoffs / "P-100.md").exists()


def test_verdict_route_accept_amended_persists_edited_text_then_handoff(brain):
    """basis='amended' persists the (human-EDITED) amended_change as a FRESH
    amended_draft BEFORE recording, so the governed/handoff form is that final
    edited text. Accept returns a handoff_path and basis='amended'."""
    brain.seed(FW_PROP)
    bs.generate_card(bs.proposal_first("P-100"))  # card from the default JSON stub
    code, obj = _post("P-100", "verdict",
                      {"verdict": "accept", "note": "ship amended",
                       "basis": "amended",
                       "actor_id": "oracle",
                       "amended_change": "Final edited amended change text."})
    assert code == 200
    assert obj["ok"] is True and obj["basis"] == "amended"
    assert obj["actor"]["id"] == "oracle"
    assert obj["handoff_path"] == "handoffs/P-100.md"

    # a fresh amended_draft carrying the EDITED text was persisted
    latest = bs.latest_amended_draft("P-100")
    assert latest["change"] == "Final edited amended change text."
    # and the handoff body is that edited text
    handoff = (brain.handoffs / "P-100.md").read_text()
    assert "**Actor:** `oracle` (agent; ui-asserted, not cryptographically authenticated)" in handoff
    body = _handoff_body(handoff)
    assert "Final edited amended change text." in body


def test_verdict_route_amended_requires_amended_change(brain):
    """basis='amended' with no amended_change is a clean 400 — nothing recorded,
    no amended_draft persisted."""
    brain.seed(FW_PROP)
    code, obj = _post("P-100", "verdict",
                      {"verdict": "accept", "note": "x", "basis": "amended",
                       "actor_id": "derrick"})
    assert code == 400
    assert bs.latest_amended_draft("P-100") is None
    # no verdict outcome appended (only the seeded open row remains)
    rows = [json.loads(l) for l in brain.proposals.read_text().splitlines()
            if l.strip()]
    assert len(rows) == 1


@pytest.mark.parametrize("actor_id", [None, "mallory", "human:ui"])
def test_verdict_route_rejects_missing_or_unknown_actor_before_writes(brain, actor_id):
    brain.seed(FW_PROP)
    code, obj = _post("P-100", "verdict",
                      {"verdict": "accept", "note": "x", "basis": "original",
                       "actor_id": actor_id})
    assert code == 400
    assert obj["error"] == "actor_id must be one of: derrick, oracle"
    assert len(brain.proposals.read_text().splitlines()) == 1


@pytest.mark.parametrize("actor_id", [None, "mallory"])
def test_handoff_route_rejects_missing_or_unknown_actor(brain, actor_id):
    brain.seed(FW_PROP)
    code, obj = _post("P-100", "handoff", {"basis": "original", "actor_id": actor_id})
    assert code == 400
    assert obj["error"] == "actor_id must be one of: derrick, oracle"
    assert not brain.handoffs.exists()


def test_synthesize_route_returns_amended_change(brain):
    """POST .../synthesize returns {amended_change} and persists one draft."""
    brain.seed(FW_PROP)
    bs.discuss_turn(bs.proposal_first("P-100"), "tighten it")
    brain.gemma._reply = "A crisp, self-contained amended proposal."
    code, obj = _post("P-100", "synthesize", {})
    assert code == 200
    assert obj["amended_change"] == "A crisp, self-contained amended proposal."
    assert len(brain.amended_lines()) == 1


# ---------------------------------------------------------------------------
# refresh_projection — verdict-triggered, framework-local, best-effort
# ---------------------------------------------------------------------------

def test_refresh_projection_runs_framework_projectors_in_order(brain, monkeypatch):
    """A verdict refresh re-runs project_pages -> project_map -> project_summary
    (in that order) and NOT ingest_apparatus — re-ingesting apparatus
    narratives/edges is needless on a framework verdict. Scripts resolve under the
    monkeypatched tmp ROOT, so the real projection is never touched."""
    ran = []

    def fake_run(cmd, **kw):
        ran.append(Path(cmd[1]).name)
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(bs.subprocess, "run", fake_run)
    bs.refresh_projection()
    assert ran == ["project_pages.py", "project_map.py", "project_summary.py"]
    assert "ingest_apparatus.py" not in ran  # no needless apparatus re-ingest


def test_refresh_projection_swallows_subprocess_errors(brain, monkeypatch):
    """refresh_projection is best-effort: a projector that raises must NOT
    propagate (a recorded verdict cannot be undone by a projection hiccup)."""
    def boom(cmd, **kw):
        raise OSError("projector unavailable")

    monkeypatch.setattr(bs.subprocess, "run", boom)
    bs.refresh_projection()  # must return cleanly, not raise


def test_verdict_route_schedules_a_refresh(brain, monkeypatch):
    """A successful verdict via the route fires the refresh scheduler exactly once
    (the fixture stubbed it to a no-op; here we count the calls)."""
    fired = []
    monkeypatch.setattr(bs, "_schedule_refresh", lambda: fired.append(1))
    brain.seed(FW_PROP)
    code, obj = _post("P-100", "verdict",
                      {"verdict": "accept", "note": "ship it", "basis": "original",
                       "actor_id": "derrick"})
    assert code == 200 and obj["ok"] is True
    assert fired == [1]


def test_verdict_route_failed_verdict_does_not_schedule_refresh(brain, monkeypatch):
    """A rejected route call (bad basis -> 400 before recording) must NOT schedule a
    refresh — nothing changed, so nothing to reproject."""
    fired = []
    monkeypatch.setattr(bs, "_schedule_refresh", lambda: fired.append(1))
    brain.seed(FW_PROP)
    code, _ = _post("P-100", "verdict",
                    {"verdict": "accept", "note": "x", "basis": "amended",
                     "actor_id": "derrick"})  # missing amended_change
    assert code == 400
    assert fired == []


# ---------------------------------------------------------------------------
# GET /api/operations — bounded, read-only, fail-closed truth cockpit
# ---------------------------------------------------------------------------

@pytest.fixture
def operations(brain, tmp_path, monkeypatch):
    """Isolated files for the operations endpoint; nothing points at the repo."""
    run = tmp_path / "run_state"
    run.mkdir(exist_ok=True)
    view = tmp_path / "memory" / "brain" / "view"
    view.mkdir(parents=True, exist_ok=True)
    consumer = tmp_path / "consumer"
    (consumer / "run_state").mkdir(parents=True)
    monkeypatch.setattr(bs, "FRAMEWORK_STATE", run / "framework.state.json")
    monkeypatch.setattr(bs, "WATCH_PID", run / "brain-watch.pid")
    monkeypatch.setattr(bs, "WATCH_LOG", run / "brain-watch.log")
    monkeypatch.setattr(bs, "SUMMARY_JSON", view / "summary.json")
    monkeypatch.setattr(bs.ps, "resolve_consumer", lambda: consumer)
    (run / "framework.state.json").write_text(json.dumps({"harvest_watermark": {
        "a_bgt_rsi": {"run_jsonl_lines": 2, "last_commit": "abc", "last_decision": "D-1"}}}))
    (consumer / "run_state" / "week1.run.jsonl").write_text("{}\n{}\n{}\n")
    (view / "summary.json").write_text('{"generated_at":"2026-06-01T00:00:00Z"}')
    (run / "brain-watch.log").write_text(
        "[2026-06-01T00:00:01Z] pipeline ok in 1.0s\n"
        "[2026-06-01T00:01:01Z] pipeline FAIL in 2.0s\n")
    (run / "brain-watch.pid").write_text("99999999\n")
    bs._ops_cache["data"] = None
    bs._ops_cache["mono"] = 0.0
    return brain


def test_operations_reports_only_exact_lifecycle_evidence_and_mixed_rows(operations, monkeypatch):
    commit = "a" * 40
    accepted = dict(FW_PROP, verdict="accepted", status="closed")
    evidence = {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-100",
                "enactment": {"commit": commit, "paths": [".agents/skills/validate/SKILL.md"]},
                "verification": {"commit": commit, "command": "pytest -q", "result": "pass",
                                 "output_sha256": "b" * 64}}
    # A foreign row must be counted as a warning, not silently dropped.
    operations.proposals.write_text("\n".join(json.dumps(x) for x in (accepted, evidence,
                                    {"legacy": "unsupported"})) + "\n")

    def git_ok(argv, **_kwargs):
        if "diff-tree" in argv:
            return ".agents/skills/validate/SKILL.md\n", None
        if "rev-parse" in argv:
            return "deadbeef\n", None
        if "branch" in argv:
            return "ops\n", None
        return " M one-file\n", None
    monkeypatch.setattr(bs, "_run_bounded", git_ok)

    before = {p: p.read_bytes() for p in [operations.proposals, bs.FRAMEWORK_STATE,
                                           bs.WATCH_LOG, bs.SUMMARY_JSON]}
    code, body = _get("/api/operations")
    after = {p: p.read_bytes() for p in before}

    assert code == 200 and body["read_only"] is True
    assert body["server"]["alive"]["status"] == "observed"
    assert body["watcher"]["state"]["value"] == "stale"
    assert body["pipeline"]["last_success"]["value"] == "2026-06-01T00:00:01Z"
    assert body["cursors"]["consumer"]["value"]["delta_lines"] == 1
    counts = body["proposals"]["counts"]["value"]
    assert counts == {"accepted": 1, "enacted": 1, "verified": 1,
                      "unverified_or_pending": 0, "evidence_unknown": 1}
    assert body["proposals"]["counts"]["status"] == "partial"
    assert any("mixed-schema" in w for w in body["warnings"])
    assert before == after  # endpoint has no write side effect


def test_operations_rejects_recycled_live_pid_and_malformed_data(operations, monkeypatch):
    bs.WATCH_PID.write_text(f"{os.getpid()}\n")
    bs.WATCH_LOG.write_text("[not-a-time] pipeline ok in 1s\n")
    bs.SUMMARY_JSON.write_text("not json")
    operations.proposals.write_text("{bad json}\n")
    original_read = bs._read_limited

    def no_script(path, limit, **kwargs):
        if str(path).endswith(f"/{os.getpid()}/cmdline"):
            return "python\x00other_program.py", False, None
        return original_read(path, limit, **kwargs)
    monkeypatch.setattr(bs, "_read_limited", no_script)

    body = bs.operations_snapshot()
    assert body["watcher"]["state"]["value"] == "stale"
    assert body["pipeline"]["last_success"]["status"] == "unknown"
    assert body["projection"]["generated_at"]["status"] == "unknown"
    assert body["proposals"]["counts"]["value"]["accepted"] == 0
    assert any("malformed" in warning for warning in body["warnings"])


def test_operations_subprocess_failure_fails_closed(operations, monkeypatch):
    operations.seed(dict(FW_PROP, verdict="accepted", status="closed"),
                    {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-100",
                     "enactment": {"commit": "a" * 40, "paths": ["x"]}})
    monkeypatch.setattr(bs, "_run_bounded", lambda argv, **_kwargs: (None, "TimeoutExpired"))
    body = bs.operations_snapshot()
    assert body["repo"]["head"]["status"] == "unknown"
    assert body["proposals"]["counts"]["status"] == "partial"
    assert body["proposals"]["counts"]["value"]["enacted"] == 0
    assert body["proposals"]["counts"]["value"]["evidence_unknown"] == 1


def test_operations_skill_enactment_requires_exact_skill_contract_not_readme(operations, monkeypatch):
    commit = "a" * 40
    operations.seed(
        dict(FW_PROP, verdict="accepted", status="closed"),
        {"timestamp": "2026-06-02T00:00:00Z", "proposal_id": "P-100",
         "enactment": {"commit": commit, "paths": ["README.md"]}},
    )

    def git_readme(argv, **_kwargs):
        if "diff-tree" in argv:
            return "README.md\n", None
        return "main\n", None
    monkeypatch.setattr(bs, "_run_bounded", git_readme)
    body = bs.operations_snapshot()
    counts = body["proposals"]["counts"]["value"]
    assert counts["accepted"] == 1
    assert counts["enacted"] == counts["verified"] == 0
    assert counts["unverified_or_pending"] == 1


def test_operations_enforces_shared_budget_probe_cap_and_short_cache(operations, monkeypatch):
    rows = []
    for number in range(20):
        pid = f"P-{100 + number}"
        rows.append(dict(FW_PROP, proposal_id=pid, verdict="accepted", status="closed"))
        rows.append({"timestamp": "2026-06-02T00:00:00Z", "proposal_id": pid,
                     "enactment": {"commit": f"{number:040x}", "paths": ["README.md"]}})
    operations.seed(*rows)
    seen = []

    def bounded(argv, **kwargs):
        seen.append((argv, kwargs))
        assert kwargs["deadline"] - time.monotonic() <= bs.OPS_TOTAL_BUDGET_S
        return "README.md\n", None
    monkeypatch.setattr(bs, "_run_bounded", bounded)

    first = bs.operations_snapshot()
    probes = [argv for argv, _ in seen if "diff-tree" in argv]
    assert len(probes) == bs.OPS_MAX_LIFECYCLE_PROPOSALS == 12
    assert first["proposals"]["counts"]["value"]["evidence_unknown"] == 8
    calls_after_first = len(seen)
    second = bs.operations_snapshot()
    assert second["poll"]["value"] == "cached"
    assert len(seen) == calls_after_first  # cache prevents concurrent-poll multiplication


def test_operations_repo_is_tracked_only_and_disables_git_locks(operations, monkeypatch):
    seen = []

    def bounded(argv, **kwargs):
        seen.append((argv, kwargs))
        return "main\n", None
    monkeypatch.setattr(bs, "_run_bounded", bounded)
    body = bs.operations_snapshot()
    status_call, status_kwargs = next((a, k) for a, k in seen if "status" in a)
    assert "--untracked-files=no" in status_call
    assert status_kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
    assert "untracked files" in body["repo"]["tracked_dirty_count"]["uncertainty"]


def test_operations_cursor_payload_is_numeric_only(operations, monkeypatch):
    monkeypatch.setattr(bs, "_run_bounded", lambda argv, **_kwargs: ("main\n", None))
    cursors = bs.operations_snapshot()["cursors"]
    assert cursors["framework_harvest"]["value"] == {"run_jsonl_lines": 2}
    assert cursors["consumer"]["value"] == {"lines": 3, "watermark_lines": 2, "delta_lines": 1}


def test_cursor_streams_more_than_one_mebibyte_without_retaining_contents(tmp_path):
    path = tmp_path / "week1.run.jsonl"
    rows = 600_000
    path.write_bytes(b"{}\n" * rows)  # 1.8 MiB: exceeds the ordinary 1 MiB read budget
    count, error = bs._count_lines_bounded(path, bs.OPS_CURSOR_BYTES,
                                            deadline=time.monotonic() + 3)
    assert error is None
    assert count == rows


def test_cursor_counter_fails_closed_at_cap_or_expired_deadline(tmp_path):
    path = tmp_path / "week1.run.jsonl"
    path.write_bytes(b"{}\n" * 10)
    assert bs._count_lines_bounded(path, 5, deadline=time.monotonic() + 3) == (None, "byte_limit")
    assert bs._count_lines_bounded(path, bs.OPS_CURSOR_BYTES,
                                   deadline=time.monotonic() - 1) == (None, "budget_exhausted")


def test_operations_requires_exact_watcher_argv_and_timezone_aware_timestamps(operations, monkeypatch):
    bs.WATCH_PID.write_text(f"{os.getpid()}\n")
    bs.WATCH_LOG.write_text("[2026-06-01T00:00:01] pipeline ok in 1s\n")  # naive
    bs.SUMMARY_JSON.write_text('{"generated_at":"2026-06-01T00:00:00"}')  # naive
    operations.proposals.write_text(json.dumps({
        "timestamp": "2026-06-01T00:00:00", "proposal_id": "P-100",
        "status": "open", "change": "x"}) + "\n")
    original_read = bs._read_limited

    def deceptive_cmdline(path, limit, **kwargs):
        if str(path).endswith(f"/{os.getpid()}/cmdline"):
            return "/usr/bin/python\x00/tmp/not-watch_brain.py.bak", False, None
        return original_read(path, limit, **kwargs)
    monkeypatch.setattr(bs, "_read_limited", deceptive_cmdline)
    monkeypatch.setattr(bs, "_run_bounded", lambda argv, **_kwargs: ("main\n", None))

    body = bs.operations_snapshot()
    assert body["watcher"]["state"]["value"] == "stale"
    assert body["pipeline"]["last_success"]["status"] == "unknown"
    assert body["projection"]["generated_at"]["status"] == "unknown"
    assert body["proposals"]["counts"]["status"] == "partial"
    assert body["proposals"]["counts"]["value"]["evidence_unknown"] == 1
