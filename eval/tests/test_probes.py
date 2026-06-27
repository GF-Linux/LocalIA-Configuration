import json
import pytest
from evallib.probes import load_probes

def _write(tmp_path, rows):
    p = tmp_path / "p.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    return str(p)

_OK = {"id": "p1", "code": "open('f')", "lang": "python",
       "teaching_point": "fechar arquivo", "should_skip": False}

def test_loads_valid_probe(tmp_path):
    assert len(load_probes(_write(tmp_path, [_OK]))) == 1

def test_rejects_missing_field(tmp_path):
    bad = {k: v for k, v in _OK.items() if k != "teaching_point"}
    with pytest.raises(ValueError):
        load_probes(_write(tmp_path, [bad]))

def test_rejects_non_bool_should_skip(tmp_path):
    bad = {**_OK, "should_skip": "no"}
    with pytest.raises(ValueError):
        load_probes(_write(tmp_path, [bad]))

def test_rejects_empty_code(tmp_path):
    bad = {**_OK, "code": ""}
    with pytest.raises(ValueError):
        load_probes(_write(tmp_path, [bad]))

def test_real_probes_file_is_valid():
    probes = load_probes("data/probes.jsonl")
    assert len(probes) >= 30
    # deve haver pelo menos alguns casos "deve calar" e alguns ensináveis
    assert any(p["should_skip"] for p in probes)
    assert any(not p["should_skip"] for p in probes)
