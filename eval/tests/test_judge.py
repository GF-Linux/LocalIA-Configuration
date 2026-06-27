import pytest
from evallib.judge import extract_text, make_claude_ask, JUDGE_MODEL

class _Block:
    def __init__(self, type, text=""):
        self.type = type
        self.text = text

class _Resp:
    def __init__(self, blocks):
        self.content = blocks

def test_judge_model_is_opus_4_8():
    assert JUDGE_MODEL == "claude-opus-4-8"

def test_extract_text_concatenates_text_blocks_only():
    resp = _Resp([_Block("thinking", "ignora"), _Block("text", "ola "), _Block("text", "mundo")])
    assert extract_text(resp) == "ola mundo"

def test_extract_text_empty_when_no_text_blocks():
    assert extract_text(_Resp([_Block("thinking", "x")])) == ""

def test_make_claude_ask_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        make_claude_ask()
