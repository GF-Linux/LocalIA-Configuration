from datagen.prompts import (
    HINT_SYSTEM, PANORAMA_SYSTEM, build_hint_messages,
    build_panorama_messages, is_valid_panorama, parse_panorama,
)
from ftlib.format_chatml import TUTOR_SYSTEM

def test_hint_system_is_canonical_tutor_system():
    assert HINT_SYSTEM == TUTOR_SYSTEM

def test_build_hint_messages_mirrors_training_distribution():
    msgs = build_hint_messages("print(x)", "python")
    assert msgs[0] == {"role": "system", "content": TUTOR_SYSTEM}
    assert msgs[1] == {"role": "user", "content": "Linguagem: python\nCódigo:\nprint(x)"}

def test_build_panorama_messages_shape():
    msgs = build_panorama_messages("def a():\n def b():", "python")
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == PANORAMA_SYSTEM
    assert msgs[1] == {"role": "user",
                       "content": "Linguagem: python\nEsqueleto do arquivo:\ndef a():\n def b():"}

def test_panorama_system_mentions_structure_next_and_skip():
    assert '"structure"' in PANORAMA_SYSTEM
    assert '"next"' in PANORAMA_SYSTEM
    assert '{"skip": true}' in PANORAMA_SYSTEM

def test_is_valid_panorama_accepts_full_and_skip():
    assert is_valid_panorama({"structure": "s", "next": "n"})
    assert is_valid_panorama({"skip": True})

def test_is_valid_panorama_rejects_bad():
    assert not is_valid_panorama({"structure": "s"})
    assert not is_valid_panorama({"structure": "", "next": "n"})
    assert not is_valid_panorama("nope")
    assert not is_valid_panorama(None)

def test_parse_panorama_strict_extracts_or_none():
    assert parse_panorama('lixo {"structure":"s","next":"n"} fim') == {"structure": "s", "next": "n"}
    assert parse_panorama('{"skip": true}') is None
    assert parse_panorama("sem json") is None
