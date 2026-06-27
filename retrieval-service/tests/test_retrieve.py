from app.zim_search import ZimSearch
from app.retrieve import build_results

def test_build_results_shape_and_grounding(tiny_zim):
    zs = ZimSearch(tiny_zim)
    results = build_results(zs, "read file open", k=3)
    assert isinstance(results, list) and len(results) >= 1
    r = results[0]
    assert set(r.keys()) == {"title", "url", "snippet"}
    assert "read a file" in r["title"].lower()
    assert "with open" in r["snippet"].lower()  # snippet sem tags HTML

def test_build_results_empty_query(tiny_zim):
    assert build_results(ZimSearch(tiny_zim), "", k=3) == []

def test_retrieve_endpoint(tiny_zim, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "_get_search", lambda: ZimSearch(tiny_zim))
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    r = client.get("/retrieve", params={"q": "read file open", "k": 2})
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1 and "snippet" in data[0]

def test_retrieve_clamps_k(tiny_zim, monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "_get_search", lambda: ZimSearch(tiny_zim))
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    r = client.get("/retrieve", params={"q": "python", "k": 999})
    assert r.status_code == 200  # k acima do máximo não quebra
