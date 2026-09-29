"""Offline deployed-window budgeting for the brain drafting client."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import brain_server as bs


def _config(context=32768):
    return {"base_url": "http://127.0.0.1:30080/v1", "model": "selected", "context_length": context}


def test_context_bundle_has_no_fixed_skill_finding_or_rule_clips(tmp_path, monkeypatch):
    skill = tmp_path / "skills" / "validate" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("S" * 4001)
    feedback = tmp_path / "feedback.jsonl"
    feedback.write_text("\n".join(json.dumps({"skill": "validate", "class": "x", "evidence": "E" * 300}) for _ in range(9)))
    rules = tmp_path / "rules.md"
    rules.write_text("R" * 1801)
    monkeypatch.setattr(bs, "SKILLS", tmp_path / "skills")
    monkeypatch.setattr(bs, "FEEDBACK", feedback)
    monkeypatch.setattr(bs, "RULES", rules)

    context = bs.context_for({"target": "validate", "target_type": "skill"})
    assert "S" * 4001 in context and context.count("E" * 300) == 9 and "R" * 1801 in context


def test_selected_window_preserves_all_history_when_it_fits(monkeypatch):
    messages = [{"role": "system", "content": "s"}, *[
        {"role": "user" if i % 2 == 0 else "assistant", "content": "turn" + str(i)}
        for i in range(30)], {"role": "user", "content": "current"}]
    monkeypatch.setattr(bs, "message_tokens", lambda msgs, _config: len(msgs))
    assert bs.fit_context(messages, max_tokens=8192, config=_config(32768)) == messages


def test_history_only_trims_after_real_budget_is_reached(monkeypatch):
    messages = [{"role": "system", "content": "system"},
                {"role": "user", "content": "old"},
                {"role": "assistant", "content": "old-answer"},
                {"role": "user", "content": "newer"},
                {"role": "assistant", "content": "newer-answer"},
                {"role": "user", "content": "current"}]
    monkeypatch.setattr(bs, "message_tokens", lambda msgs, _config: len(msgs) * 10)
    fitted = bs.fit_context(messages, max_tokens=50, config=_config(100))
    assert fitted == [messages[0], *messages[3:]]
    assert [message["role"] for message in fitted] == ["system", "user", "assistant", "user"]


def test_overflow_of_retained_current_request_is_not_silently_altered(monkeypatch):
    messages = [{"role": "system", "content": "system"},
                {"role": "user", "content": "the complete current request"}]
    monkeypatch.setattr(bs, "message_tokens", lambda *_args: 21)
    with pytest.raises(bs.GemmaError, match="retained system and current"):
        bs.fit_context(messages, max_tokens=80, config=_config(100))
    assert messages[-1]["content"] == "the complete current request"


def test_message_tokenization_uses_the_actual_chat_payload(monkeypatch):
    messages = [{"role": "system", "content": "system"},
                {"role": "user", "content": "current"}]
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"count":19}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        assert timeout == 3
        return Response()

    monkeypatch.setattr(bs.urllib.request, "urlopen", fake_urlopen)
    assert bs.message_tokens(messages, _config()) == 19
    assert captured == {
        "url": "http://127.0.0.1:30080/tokenize",
        "payload": {
            "model": "selected", "messages": messages,
            "chat_template_kwargs": {"enable_thinking": False},
            "add_generation_prompt": True,
        },
    }


@pytest.mark.parametrize("response_body", [b"null", b"[]", b'{"count":true}'])
def test_malformed_tokenizer_response_uses_conservative_fallback(monkeypatch, response_body):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return response_body

    monkeypatch.setattr(bs.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    messages = [{"role": "user", "content": "current"}]
    assert bs.message_tokens(messages, _config()) >= bs._TOKENIZE_TEMPLATE_MARGIN_BYTES


def test_manifest_selects_current_or_future_actual_context(tmp_path, monkeypatch):
    lab = tmp_path / "lab"
    (lab / "config").mkdir(parents=True)
    manifest = lab / "config" / "model_deployment.json"
    manifest.write_text(json.dumps({"base_url": "http://127.0.0.1:30080/v1", "model": "current", "context_length": 32768}))
    monkeypatch.setenv("ORACLE_LAB", str(lab))
    monkeypatch.delenv("BRAIN_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("BRAIN_LLM_MODEL", raising=False)
    monkeypatch.setenv("BRAIN_LLM_CONTEXT_LENGTH", "1024")
    assert bs.drafting_config()["context_length"] == 32768
    manifest.write_text(json.dumps({"base_url": "http://127.0.0.1:30080/v1", "model": "future", "context_length": 262144}))
    assert bs.drafting_config()["context_length"] == 262144


@pytest.mark.parametrize("manifest", [
    {"base_url": "not-a-url", "model": "current", "context_length": 32768},
    {"base_url": "http://127.0.0.1:30080/v1", "model": "", "context_length": 32768},
    {"base_url": "http://127.0.0.1:30080/v1", "model": "current", "context_length": 0},
    {"base_url": "http://127.0.0.1:30080/v1", "model": "current", "context_length": 32768.5},
    {"base_url": "http://127.0.0.1:30080/v1", "model": "current", "context_length": True},
    [],
])
def test_manifest_requires_valid_endpoint_model_and_positive_context(tmp_path, monkeypatch, manifest):
    lab = tmp_path / "lab"
    (lab / "config").mkdir(parents=True)
    (lab / "config" / "model_deployment.json").write_text(json.dumps(manifest))
    monkeypatch.setenv("ORACLE_LAB", str(lab))
    monkeypatch.delenv("BRAIN_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("BRAIN_LLM_MODEL", raising=False)
    with pytest.raises(bs.GemmaError):
        bs.drafting_config()


def test_custom_endpoint_requires_declared_or_probed_context(monkeypatch):
    monkeypatch.setenv("BRAIN_LLM_BASE_URL", "http://127.0.0.1:9999/v1")
    monkeypatch.delenv("BRAIN_LLM_CONTEXT_LENGTH", raising=False)
    def unavailable(*_args, **_kwargs):
        raise OSError("offline")
    monkeypatch.setattr(bs.urllib.request, "urlopen", unavailable)
    with pytest.raises(bs.GemmaError, match="trustworthy context"):
        bs.drafting_config()


@pytest.mark.parametrize("context_length", [True, 32768.5])
def test_custom_probe_rejects_noninteger_context_length(monkeypatch, context_length):
    monkeypatch.setenv("BRAIN_LLM_BASE_URL", "http://127.0.0.1:9999/v1")
    monkeypatch.delenv("BRAIN_LLM_CONTEXT_LENGTH", raising=False)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"context_length": context_length}).encode()

    monkeypatch.setattr(bs.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(bs.GemmaError, match="trustworthy context"):
        bs.drafting_config()
