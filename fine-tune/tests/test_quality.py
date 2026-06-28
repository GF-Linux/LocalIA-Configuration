from datagen.quality import normalize_code, dedup, counts_by, balance_by_ratio

def test_normalize_code_collapses_whitespace():
    assert normalize_code("def f():\n    return 1") == "def f(): return 1"

def test_dedup_removes_whitespace_variants_keeps_order():
    rows = [
        {"code": "def f():\n    return 1"},
        {"code": "def f():\n        return 1"},  # dup (só whitespace)
        {"code": "def g():\n    return 2"},
    ]
    out = dedup(rows)
    assert [r["code"] for r in out] == ["def f():\n    return 1", "def g():\n    return 2"]

def test_dedup_with_custom_key_on_outline():
    rows = [{"outline": "a"}, {"outline": "a"}, {"outline": "b"}]
    assert len(dedup(rows)) == 2

def test_counts_by_lang():
    rows = [{"lang": "python"}, {"lang": "go"}, {"lang": "python"}]
    assert counts_by(rows, lambda r: r["lang"]) == {"python": 2, "go": 1}

def test_balance_by_ratio_caps_skip_fraction():
    # 8 skip + 2 ensina; teto skip = 0.5 -> mantém no máximo 2 skip (2/(2+2)=0.5)
    rows = [{"id": i, "skip": True} for i in range(8)] + [{"id": 100 + i, "skip": False} for i in range(2)]
    out = balance_by_ratio(rows, lambda r: r["skip"], 0.5, seed=1)
    n_skip = sum(1 for r in out if r["skip"])
    n_keep = len(out)
    assert n_skip == 2 and n_keep == 4
    assert n_skip / n_keep <= 0.5

def test_balance_by_ratio_no_op_when_under_cap():
    rows = [{"skip": True}, {"skip": False}, {"skip": False}]
    out = balance_by_ratio(rows, lambda r: r["skip"], 0.5, seed=0)
    assert out == rows

def test_balance_by_ratio_deterministic():
    rows = [{"id": i, "skip": True} for i in range(10)] + [{"id": 99, "skip": False}]
    a = balance_by_ratio(rows, lambda r: r["skip"], 0.5, seed=3)
    b = balance_by_ratio(rows, lambda r: r["skip"], 0.5, seed=3)
    assert a == b
