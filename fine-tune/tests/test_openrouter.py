import os
import pytest
from datagen.openrouter import build_body, parse_completion, make_glm_ask, GLM_MODEL, OPENROUTER_URL

def test_build_body_shape():
    body = build_body("z-ai/glm-5.2", [{"role": "user", "content": "oi"}])
    assert body["model"] == "z-ai/glm-5.2"
    assert body["messages"] == [{"role": "user", "content": "oi"}]
    assert body["stream"] is False

def test_parse_completion_extracts_content_and_usage():
    resp = {"choices": [{"message": {"content": "olá"}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 7}}
    content, usage = parse_completion(resp)
    assert content == "olá"
    assert usage == {"prompt_tokens": 12, "completion_tokens": 7}

def test_parse_completion_missing_usage_defaults_zero():
    resp = {"choices": [{"message": {"content": "x"}}]}
    _, usage = parse_completion(resp)
    assert usage == {"prompt_tokens": 0, "completion_tokens": 0}

def test_make_glm_ask_requires_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        make_glm_ask()

def test_ask_returns_content_and_reports_usage(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    seen = []
    def transport(url, body):
        assert url == OPENROUTER_URL and body["model"] == GLM_MODEL
        return 200, {"choices": [{"message": {"content": "R"}}],
                     "usage": {"prompt_tokens": 3, "completion_tokens": 4}}
    ask = make_glm_ask(transport=transport, on_usage=seen.append)
    assert ask([{"role": "user", "content": "q"}]) == "R"
    assert seen == [{"prompt_tokens": 3, "completion_tokens": 4}]

def test_ask_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    calls = {"n": 0}
    slept = []
    def transport(url, body):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, {}
        return 200, {"choices": [{"message": {"content": "ok"}}],
                     "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    ask = make_glm_ask(transport=transport, sleep=slept.append)
    assert ask([{"role": "user", "content": "q"}]) == "ok"
    assert calls["n"] == 2 and len(slept) == 1

def test_ask_gives_up_after_retries(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    def transport(url, body):
        return 503, {}
    ask = make_glm_ask(transport=transport, retries=3, sleep=lambda s: None)
    with pytest.raises(RuntimeError, match="após 3 tentativas"):
        ask([{"role": "user", "content": "q"}])
