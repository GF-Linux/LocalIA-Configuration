from ftlib.collect_oci import normalize_oci_row

def test_normalizes_valid_row():
    r = normalize_oci_row({"input": "Write a function", "output": "def f(): pass", "domain": "generic"})
    assert r == {"instruction": "Write a function", "response": "def f(): pass"}

def test_drops_empty():
    assert normalize_oci_row({"input": "", "output": "x"}) is None
    assert normalize_oci_row({"input": "x", "output": ""}) is None
    assert normalize_oci_row({"output": "x"}) is None
