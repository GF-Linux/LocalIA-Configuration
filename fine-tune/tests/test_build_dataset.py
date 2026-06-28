import json, os
from ftlib.build_dataset import split_deterministic, _read_jsonl, _write_jsonl, build_items

def test_split_deterministic_stable_and_partitions():
    items = list(range(100))
    train, held = split_deterministic(items, 0.15, seed=42)
    assert len(held) == 15 and len(train) == 85
    assert sorted(train + held) == items  # partição completa
    # determinismo
    t2, h2 = split_deterministic(items, 0.15, seed=42)
    assert (train, held) == (t2, h2)

def test_build_items_includes_generated_tracks(tmp_path):
    seeds_p = tmp_path / "seeds.jsonl"
    oci_p = tmp_path / "oci.jsonl"
    gh_p = tmp_path / "generated_hints.jsonl"
    gp_p = tmp_path / "generated_panorama.jsonl"
    _write_jsonl(str(seeds_p), [{"code": "a=1", "lang": "python",
        "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}])
    _write_jsonl(str(oci_p), [{"instruction": "do x", "response": "code"}])
    _write_jsonl(str(gh_p), [{"code": "open('f')", "lang": "go",
        "hint": {"comment": "c2", "why": "w2", "nudge": "n2", "suggestion": "s2"}}])
    _write_jsonl(str(gp_p), [{"outline": "def a():", "lang": "go",
        "panorama": {"structure": "s", "next": "n"}}])
    items = build_items(str(seeds_p), str(oci_p), str(gh_p), str(gp_p))
    # 1 seed + 1 oci + 1 gen-hint + 1 gen-panorama = 4
    assert len(items) == 4
    systems = [it["messages"][0]["content"] for it in items]
    from ftlib.format_chatml import TUTOR_SYSTEM, CODE_SYSTEM, PANORAMA_SYSTEM
    assert TUTOR_SYSTEM in systems and CODE_SYSTEM in systems and PANORAMA_SYSTEM in systems

def test_build_items_tolerates_missing_generated_files(tmp_path):
    seeds_p = tmp_path / "seeds.jsonl"
    oci_p = tmp_path / "oci.jsonl"
    _write_jsonl(str(seeds_p), [{"code": "a=1", "lang": "python",
        "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}])
    _write_jsonl(str(oci_p), [{"instruction": "do x", "response": "code"}])
    items = build_items(str(seeds_p), str(oci_p),
                        str(tmp_path / "nope1.jsonl"), str(tmp_path / "nope2.jsonl"))
    assert len(items) == 2
