from evallib.runners import (build_tutor_messages, generate_hints,
                             score_format, score_selectivity)
from evallib.contract import TUTOR_SYSTEM

def test_build_tutor_messages_mirrors_runtime():
    msgs = build_tutor_messages({"code": "open('f')", "lang": "python"})
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert msgs[0]["content"] == TUTOR_SYSTEM
    assert "open('f')" in msgs[1]["content"]
    assert "python" in msgs[1]["content"]

def test_generate_hints_uses_ask_per_probe():
    probes = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"}]
    replies = iter(["h1", "h2"])
    out = generate_hints(probes, lambda messages: next(replies))
    assert out == ["h1", "h2"]

def test_score_format_counts_valid_json():
    probes = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"}]
    hints = ['{"comment":"c","why":"w","nudge":"n","suggestion":"s"}', "lixo"]
    out = score_format(probes, hints)
    assert out == {"frac": 0.5, "valid": 1, "total": 2}

def test_score_selectivity_only_should_skip():
    probes = [
        {"code": "a", "lang": "python", "should_skip": True},
        {"code": "b", "lang": "python", "should_skip": True},
        {"code": "c", "lang": "python", "should_skip": False},
    ]
    hints = ['{"skip": true}', '{"comment":"c","why":"w","nudge":"n","suggestion":"s"}', "x"]
    out = score_selectivity(probes, hints)
    # 2 casos "deve calar"; só o 1º calou corretamente
    assert out == {"correct": 1, "total": 2}
