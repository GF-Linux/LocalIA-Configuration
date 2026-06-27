import json, pytest
from ftlib.collect_seeds import load_seeds

def _write(tmp_path, rows):
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return str(p)

def test_loads_valid_seeds(tmp_path):
    rows = [{"code": "open('f')", "lang": "python",
             "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}]
    assert len(load_seeds(_write(tmp_path, rows))) == 1

def test_rejects_bad_hint(tmp_path):
    rows = [{"code": "x", "lang": "python", "hint": {"comment": "c"}}]
    with pytest.raises(ValueError):
        load_seeds(_write(tmp_path, rows))

def test_rejects_empty_code(tmp_path):
    rows = [{"code": "", "lang": "python",
             "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}]
    with pytest.raises(ValueError):
        load_seeds(_write(tmp_path, rows))

def test_real_seeds_file_is_valid():
    # o arquivo real do projeto deve carregar sem erro e ter pelo menos 50 exemplos
    seeds = load_seeds("data/seeds.jsonl")
    assert len(seeds) >= 50
