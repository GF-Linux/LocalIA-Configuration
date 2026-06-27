import os
from fastapi import FastAPI
from app.config import get_zim_path
from app.zim_search import ZimSearch
from app.retrieve import build_results

app = FastAPI(title="Professor Retrieval Service")

_search: ZimSearch | None = None
MAX_K = 10


def _get_search() -> ZimSearch:
    global _search
    if _search is None:
        _search = ZimSearch(get_zim_path())  # carga preguiçosa (abre o .zim 1x)
    return _search


@app.get("/health")
def health():
    return {"status": "ok", "zim_loaded": os.path.exists(get_zim_path())}


@app.get("/retrieve")
def retrieve(q: str = "", k: int = 3):
    k = max(1, min(k, MAX_K))
    if not q.strip():
        return []
    try:
        return build_results(_get_search(), q, k)
    except Exception:
        return []  # fail-safe: nunca 500 para a extensão
