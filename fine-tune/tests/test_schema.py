from ftlib.schema import is_valid_hint, HINT_KEYS

def test_valid_full_hint():
    assert is_valid_hint({"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"})

def test_valid_skip():
    assert is_valid_hint({"skip": True})

def test_missing_field_invalid():
    assert not is_valid_hint({"comment": "c", "why": "w", "nudge": "n"})

def test_empty_field_invalid():
    assert not is_valid_hint({"comment": "", "why": "w", "nudge": "n", "suggestion": "s"})

def test_non_dict_invalid():
    assert not is_valid_hint("nope")
    assert not is_valid_hint(None)

def test_hint_keys_constant():
    assert HINT_KEYS == ("comment", "why", "nudge", "suggestion")
