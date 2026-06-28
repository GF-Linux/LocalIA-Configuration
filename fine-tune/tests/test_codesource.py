from datagen.codesource import make_outline, normalize, sample_code

def test_make_outline_short_code_unchanged():
    code = "def a():\n    return 1"
    assert make_outline(code, "python", max_lines=120) == code

def test_make_outline_long_code_keeps_only_structural_lines():
    body = "\n".join([f"    x{i} = {i}" for i in range(200)])
    code = f"import os\ndef a():\n{body}\nclass B:\n    pass"
    out = make_outline(code, "python", max_lines=10)
    assert "import os" in out
    assert "def a():" in out
    assert "class B:" in out
    assert "x100 = 100" not in out  # corpo descartado

def test_normalize_collapses_whitespace():
    assert normalize("  a   b\n\tc ") == "a b c"

def test_sample_code_filters_by_size_and_returns_code_lang():
    rows = [
        {"code": "x", "lang": "python"},               # curto demais
        {"code": "def ok():\n    return 42 + 1", "lang": "python"},
        {"code": "y" * 5000, "lang": "go"},            # longo demais
    ]
    out = sample_code(rows, n=10, min_chars=10, max_chars=2000)
    assert len(out) == 1
    assert out[0] == {"code": "def ok():\n    return 42 + 1", "lang": "python"}

def test_sample_code_dedups_by_normalized_code():
    rows = [
        {"code": "def f():\n    return 1", "lang": "python"},
        {"code": "def f():\n        return 1", "lang": "python"},  # só whitespace difere
        {"code": "def g():\n    return 2", "lang": "python"},
    ]
    out = sample_code(rows, n=10, min_chars=5, max_chars=2000)
    assert len(out) == 2

def test_sample_code_deterministic_with_seed():
    rows = [{"code": f"def f{i}():\n    return {i}", "lang": "python"} for i in range(20)]
    a = sample_code(rows, n=5, seed=7, min_chars=5)
    b = sample_code(rows, n=5, seed=7, min_chars=5)
    assert a == b

def test_sample_code_skips_rows_without_valid_lang():
    rows = [{"code": "def ok():\n    return 1", "lang": ""},
            {"code": "def ok2():\n    return 2"}]
    assert sample_code(rows, n=10, min_chars=5) == []
