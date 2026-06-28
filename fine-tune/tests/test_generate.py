import json
from datagen.generate import generate_one, generate_batch

def test_generate_one_hint_valid_kept():
    item = {"code": "open('f')", "lang": "python"}
    hint = {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}
    out = generate_one(item, lambda msgs: f"lixo {json.dumps(hint)} fim", "hint")
    assert out == {"code": "open('f')", "lang": "python", "hint": hint}

def test_generate_one_hint_skip_kept():
    item = {"code": "x=1", "lang": "python"}
    out = generate_one(item, lambda msgs: '{"skip": true}', "hint")
    assert out == {"code": "x=1", "lang": "python", "hint": {"skip": True}}

def test_generate_one_hint_invalid_dropped():
    item = {"code": "x=1", "lang": "python"}
    out = generate_one(item, lambda msgs: '{"comment": "só isso"}', "hint")
    assert out is None

def test_generate_one_hint_unparseable_dropped():
    item = {"code": "x=1", "lang": "python"}
    assert generate_one(item, lambda msgs: "sem json aqui", "hint") is None

def test_generate_one_panorama_valid_kept():
    item = {"outline": "def a():\n def b():", "lang": "python"}
    pan = {"structure": "s", "next": "n"}
    out = generate_one(item, lambda msgs: json.dumps(pan), "panorama")
    assert out == {"outline": "def a():\n def b():", "lang": "python", "panorama": pan}

def test_generate_one_panorama_skip_kept():
    item = {"outline": "x", "lang": "python"}
    out = generate_one(item, lambda msgs: '{"skip": true}', "panorama")
    assert out == {"outline": "x", "lang": "python", "panorama": {"skip": True}}

def test_generate_one_passes_correct_messages_per_kind():
    seen = {}
    def ask(msgs):
        seen["sys"] = msgs[0]["content"]
        return '{"skip": true}'
    generate_one({"code": "c", "lang": "go"}, ask, "hint")
    assert "JSON" in seen["sys"] and "professor" in seen["sys"].lower()
    generate_one({"outline": "o", "lang": "go"}, ask, "panorama")
    assert "ESQUELETO" in seen["sys"]

def test_generate_batch_keeps_only_valid():
    items = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"}]
    replies = iter(['{"comment":"c","why":"w","nudge":"n","suggestion":"s"}', "lixo"])
    out = generate_batch(items, lambda msgs: next(replies), "hint")
    assert len(out) == 1 and out[0]["code"] == "a"
