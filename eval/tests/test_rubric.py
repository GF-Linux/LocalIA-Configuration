import json
from evallib.rubric import RUBRIC_CRITERIA, build_judge_prompt, parse_verdict, score_quality

def test_criteria_constant():
    assert RUBRIC_CRITERIA == ("socratic", "why", "concision", "relevance", "correctness")

def test_build_prompt_includes_code_and_hint_and_json():
    probe = {"code": "open('f')", "lang": "python"}
    p = build_judge_prompt(probe, '{"comment":"c"}')
    assert "open('f')" in p
    assert '{"comment":"c"}' in p
    assert "json" in p.lower()
    for c in RUBRIC_CRITERIA:
        assert c in p

def test_parse_verdict_ok():
    raw = 'lixo {"scores": {"socratic":5,"why":4,"concision":3,"relevance":5,"correctness":4}, "rationale":"r"} fim'
    v = parse_verdict(raw)
    assert v["scores"]["socratic"] == 5 and v["rationale"] == "r"

def test_parse_verdict_rejects_out_of_range():
    raw = '{"scores": {"socratic":6,"why":4,"concision":3,"relevance":5,"correctness":4}, "rationale":"r"}'
    assert parse_verdict(raw) is None

def test_parse_verdict_rejects_missing_key():
    raw = '{"scores": {"socratic":5,"why":4,"concision":3,"relevance":5}, "rationale":"r"}'
    assert parse_verdict(raw) is None

def test_parse_verdict_rejects_garbage():
    assert parse_verdict("não é json") is None

def test_parse_verdict_rejects_bool_score():
    # True == 1 in Python; a bool must NOT be accepted as a score
    raw = '{"scores": {"socratic":true,"why":4,"concision":3,"relevance":5,"correctness":4}, "rationale":"r"}'
    assert parse_verdict(raw) is None

def test_parse_verdict_rejects_below_range():
    raw = '{"scores": {"socratic":0,"why":4,"concision":3,"relevance":5,"correctness":4}, "rationale":"r"}'
    assert parse_verdict(raw) is None

def test_score_quality_aggregates_valid_only():
    items = [({"code": "a", "lang": "python"}, "h1"),
             ({"code": "b", "lang": "python"}, "h2")]
    replies = iter([
        '{"scores": {"socratic":4,"why":4,"concision":4,"relevance":4,"correctness":4}, "rationale":"r"}',
        'lixo inválido',
    ])
    out = score_quality(items, lambda prompt: next(replies))
    assert out["n"] == 2 and out["valid"] == 1
    assert out["means"]["socratic"] == 4.0
    assert out["overall"] == 4.0
