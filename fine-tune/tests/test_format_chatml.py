import json
from ftlib.format_chatml import seed_to_chatml, oci_to_chatml, TUTOR_SYSTEM
from ftlib.build_dataset import split_deterministic

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
