import json
from ftlib.format_chatml import PANORAMA_SYSTEM, panorama_to_chatml, seed_to_chatml, oci_to_chatml, TUTOR_SYSTEM
from ftlib.build_dataset import split_deterministic
from datagen.prompts import PANORAMA_SYSTEM as DATAGEN_PANORAMA_SYSTEM

def test_seed_to_chatml_shape():
    seed = {"code": "open('f')", "lang": "python",
            "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}
    msg = seed_to_chatml(seed)["messages"]
    assert [m["role"] for m in msg] == ["system", "user", "assistant"]
    assert msg[0]["content"] == TUTOR_SYSTEM
    assert "open('f')" in msg[1]["content"]
    assert json.loads(msg[2]["content"]) == seed["hint"]  # assistant é JSON parseável

def test_tutor_system_mentions_json_and_pt():
    s = TUTOR_SYSTEM.lower()
    assert "json" in s and "portugu" in s

def test_oci_to_chatml_shape():
    msg = oci_to_chatml({"instruction": "Write f", "response": "def f(): pass"})["messages"]
    assert [m["role"] for m in msg] == ["system", "user", "assistant"]
    assert msg[1]["content"] == "Write f"
    assert msg[2]["content"] == "def f(): pass"

def test_split_deterministic_is_stable_and_disjoint():
    items = list(range(100))
    a1, b1 = split_deterministic(items, 0.15, seed=42)
    a2, b2 = split_deterministic(items, 0.15, seed=42)
    assert (a1, b1) == (a2, b2)            # determinístico
    assert len(b1) == 15 and len(a1) == 85 # split correto
    assert set(a1).isdisjoint(set(b1))     # sem vazamento

def test_datagen_reexports_same_panorama_constant():
    # fonte única: datagen.prompts re-exporta a MESMA constante de ftlib (mesmo objeto)
    assert DATAGEN_PANORAMA_SYSTEM is PANORAMA_SYSTEM

def test_panorama_to_chatml_shape():
    row = {"outline": "def a():\n def b():", "lang": "python",
           "panorama": {"structure": "s", "next": "n"}}
    msg = panorama_to_chatml(row)
    assert msg["messages"][0] == {"role": "system", "content": PANORAMA_SYSTEM}
    assert msg["messages"][1] == {"role": "user",
        "content": "Linguagem: python\nEsqueleto do arquivo:\ndef a():\n def b():"}
    assert json.loads(msg["messages"][2]["content"]) == {"structure": "s", "next": "n"}

def test_panorama_to_chatml_skip():
    row = {"outline": "x", "lang": "go", "panorama": {"skip": True}}
    msg = panorama_to_chatml(row)
    assert json.loads(msg["messages"][2]["content"]) == {"skip": True}

def test_seed_to_chatml_still_handles_generated_hint_shape():
    row = {"code": "open('f')", "lang": "python",
           "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}
    msg = seed_to_chatml(row)
    assert msg["messages"][0]["content"] == TUTOR_SYSTEM
    assert json.loads(msg["messages"][2]["content"])["comment"] == "c"
