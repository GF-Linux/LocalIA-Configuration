from evallib.contract import is_valid_hint, TUTOR_SYSTEM, extract_json

def test_reexports_is_valid_hint():
    assert is_valid_hint({"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"})
    assert not is_valid_hint({"comment": "c"})

def test_reexports_tutor_system_pt_json():
    s = TUTOR_SYSTEM.lower()
    assert "json" in s and "portugu" in s

def test_reexports_extract_json_tolerates_junk():
    assert extract_json('lixo {"a": 1} fim') == {"a": 1}
    assert extract_json("sem json") is None
