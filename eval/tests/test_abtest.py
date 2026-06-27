import random
from evallib.abtest import build_pair, parse_choice, compare

def test_build_pair_is_blind_and_maps_back():
    probe = {"code": "x=1", "lang": "python"}
    prompt, mapping = build_pair(probe, "DICA_FT", "DICA_BASE", random.Random(0))
    assert "DICA_FT" in prompt and "DICA_BASE" in prompt
    assert "x=1" in prompt
    assert set(mapping.keys()) == {"A", "B"}
    assert set(mapping.values()) == {"ft", "base"}
    # cego: o prompt usa rótulos A/B, não revela qual modelo é qual
    assert "ft" not in prompt and "base" not in prompt

def test_build_pair_deterministic_with_same_rng():
    probe = {"code": "x", "lang": "python"}
    a = build_pair(probe, "F", "B", random.Random(42))[1]
    b = build_pair(probe, "F", "B", random.Random(42))[1]
    assert a == b

def test_parse_choice():
    assert parse_choice('{"winner": "A"}') == "A"
    assert parse_choice('lixo {"winner":"tie"} fim') == "tie"
    assert parse_choice('{"winner": "C"}') is None
    assert parse_choice("nada") is None

def test_compare_tally_deanonymizes():
    probes = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"},
              {"code": "c", "lang": "python"}]
    hints_ft = ["ft0", "ft1", "ft2"]
    hints_base = ["b0", "b1", "b2"]
    # juiz sempre escolhe o rótulo que contém o texto "ft"
    def ask(prompt):
        # encontra qual rótulo (A/B) precede o texto que tem 'ft'
        ia, ib = prompt.index("Resposta A"), prompt.index("Resposta B")
        a_text = prompt[ia:ib]
        return '{"winner": "A"}' if "ft" in a_text else '{"winner": "B"}'
    out = compare(probes, hints_ft, hints_base, ask, seed=1)
    assert out["n"] == 3 and out["valid"] == 3
    assert out["ft_wins"] == 3 and out["base_wins"] == 0 and out["ties"] == 0
