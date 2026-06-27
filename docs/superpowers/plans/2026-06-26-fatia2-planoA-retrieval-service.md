# Fatia 2 — Plano A: Serviço de retrieval do StackOverflow (servidor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um serviço HTTP (FastAPI) que recebe uma query e devolve as melhores perguntas/respostas do StackOverflow offline (`.zim`) como JSON limpo `[{title, url, snippet}]`, para a extensão Professor fundamentar suas dicas.

**Architecture:** Python/FastAPI no servidor (Francesca), lendo o `.zim` de 80GB com `python-libzim` (busca full-text nativa). A lógica difícil vive em módulos puros (extração de snippet) ou finos sobre o libzim (busca), testados isoladamente; a casca FastAPI só orquestra. Roda como serviço, no mesmo padrão do ankivet.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, `python-libzim` (≥3.4), pytest, httpx (TestClient).

## Global Constraints

- 100% local: o serviço só lê o `.zim`; nenhuma chamada de nuvem.
- Caminho do `.zim` é **configurável** via env `PROFESSOR_ZIM_PATH` (default no servidor: `C:\acervo-llm\kiwix\stackoverflow.com_en_all_2023-11.zim`).
- Endpoint principal: `GET /retrieve?q=<str>&k=<int>` → `[{title, url, snippet}]` (lista, possivelmente vazia). Default `k=3`, máximo `k=10`.
- Saúde: `GET /health` → `{"status": "ok", "zim_loaded": <bool>}`.
- **Fail-safe:** query vazia ou sem resultados → `[]` (HTTP 200), nunca 500. Erro de leitura de uma entrada → pula aquela entrada, não derruba a resposta.
- A query do StackOverflow é em **inglês** (o `.zim` é inglês).
- Contrato de resultado: `RetrievalResult = {"title": str, "url": str, "snippet": str}`. `url` = path da entrada no `.zim` (ex.: `questions/12345/...`), para visualização futura via kiwix-serve.
- Reaproveitamento: motor de busca = `python-libzim` (`Query`/`Searcher`); lógica de snippet pode espelhar `llm-tools-kiwix` (Apache-2.0), mas escrita aqui (sem dependência de runtime dele).

---

### Task 1: Scaffold do serviço + /health + harness de testes

**Files:**
- Create: `retrieval-service/requirements.txt`
- Create: `retrieval-service/app/__init__.py`
- Create: `retrieval-service/app/config.py`
- Create: `retrieval-service/app/main.py`
- Create: `retrieval-service/tests/__init__.py`
- Test: `retrieval-service/tests/test_health.py`
- Create: `retrieval-service/.gitignore`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `app.config.get_zim_path() -> str` (lê `PROFESSOR_ZIM_PATH`, com default do servidor)
  - `app.main.app` (FastAPI) com `GET /health` → `{"status": "ok", "zim_loaded": bool}`

- [ ] **Step 1: Write the failing test**

`retrieval-service/tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "zim_loaded" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run (de `retrieval-service/`): `python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 3: Create the project files**

`retrieval-service/requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
libzim>=3.4.0
httpx==0.27.0
pytest==8.2.0
```

`retrieval-service/.gitignore`:
```
__pycache__/
*.pyc
.venv/
tests/fixtures/*.zim
```

`retrieval-service/app/__init__.py`: (vazio)

`retrieval-service/tests/__init__.py`: (vazio)

`retrieval-service/app/config.py`:
```python
import os

DEFAULT_ZIM_PATH = r"C:\acervo-llm\kiwix\stackoverflow.com_en_all_2023-11.zim"

def get_zim_path() -> str:
    return os.environ.get("PROFESSOR_ZIM_PATH", DEFAULT_ZIM_PATH)
```

`retrieval-service/app/main.py`:
```python
import os
from fastapi import FastAPI
from app.config import get_zim_path

app = FastAPI(title="Professor Retrieval Service")

@app.get("/health")
def health():
    return {"status": "ok", "zim_loaded": os.path.exists(get_zim_path())}
```

- [ ] **Step 4: Install deps and run test to verify it passes**

Run (de `retrieval-service/`): `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python -m pytest tests/test_health.py -v`
Expected: PASS (1 test). (`zim_loaded` será `false` na máquina de dev sem o `.zim` — tudo bem, o teste só checa a chave.)

- [ ] **Step 5: Commit**

```bash
git add retrieval-service/
git commit -m "feat(retrieval): scaffold FastAPI service + /health"
```

---

### Task 2: Extração de snippet — módulo puro

**Files:**
- Create: `retrieval-service/app/snippet.py`
- Test: `retrieval-service/tests/test_snippet.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `app.snippet.strip_html(html: str) -> str` — remove tags HTML, colapsa espaços.
  - `app.snippet.extract_snippet(text: str, query: str, max_chars: int = 240) -> str` — janela de texto em torno do 1º termo da query encontrado; se nenhum termo casar, devolve o começo do texto (até `max_chars`).

- [ ] **Step 1: Write the failing test**

`retrieval-service/tests/test_snippet.py`:
```python
from app.snippet import strip_html, extract_snippet

def test_strip_html_removes_tags_and_collapses_space():
    assert strip_html("<p>use  <b>with</b>\n open()</p>") == "use with open()"

def test_extract_snippet_centers_on_query_term():
    text = "A" * 300 + " usar with open para arquivos " + "B" * 300
    snip = extract_snippet(text, "with open", max_chars=60)
    assert "with open" in snip
    assert len(snip) <= 60 + 1  # tolera reticências

def test_extract_snippet_falls_back_to_start():
    text = "comeco do texto sem o termo procurado aqui"
    snip = extract_snippet(text, "xyzzy", max_chars=20)
    assert snip.startswith("comeco do texto")
    assert len(snip) <= 21

def test_extract_snippet_empty_text():
    assert extract_snippet("", "qualquer") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_snippet.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`retrieval-service/app/snippet.py`:
```python
import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

def strip_html(html: str) -> str:
    return _WS.sub(" ", _TAG.sub(" ", html)).strip()

def extract_snippet(text: str, query: str, max_chars: int = 240) -> str:
    if not text:
        return ""
    lower = text.lower()
    pos = -1
    for term in query.lower().split():
        pos = lower.find(term)
        if pos != -1:
            break
    if pos == -1:
        snip = text[:max_chars]
        return snip + ("…" if len(text) > max_chars else "")
    start = max(0, pos - max_chars // 3)
    end = min(len(text), start + max_chars)
    snip = text[start:end]
    if start > 0:
        snip = "…" + snip
    if end < len(text):
        snip = snip + "…"
    return snip
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_snippet.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add retrieval-service/app/snippet.py retrieval-service/tests/test_snippet.py
git commit -m "feat(retrieval): pure HTML-strip + snippet extraction"
```

---

### Task 3: Busca no `.zim` via python-libzim

**Files:**
- Create: `retrieval-service/app/zim_search.py`
- Create: `retrieval-service/tests/conftest.py`
- Test: `retrieval-service/tests/test_zim_search.py`

**Interfaces:**
- Consumes: nada (usa `libzim` diretamente).
- Produces:
  - `app.zim_search.SearchHit` — dataclass `{path: str, title: str}`.
  - `app.zim_search.ZimSearch` — classe:
    - `__init__(self, zim_path: str)` — abre o `Archive`.
    - `search(self, query: str, k: int) -> list[SearchHit]` — full-text; lista vazia se nada.
    - `get_content(self, path: str) -> str` — HTML cru da entrada (`""` se falhar).

**Nota de teste:** o teste usa um `.zim` pequeno de fixture com índice full-text. O `conftest.py` cria um `.zim` mínimo programaticamente com `libzim.writer.Creator` (indexação ligada). Isso evita depender do `.zim` de 80GB e roda em qualquer máquina.

- [ ] **Step 1: Write the fixture + failing test**

`retrieval-service/tests/conftest.py`:
```python
import pytest
from libzim.writer import Creator, Item, StringProvider, Hint

class _Article(Item):
    def __init__(self, path, title, html):
        super().__init__()
        self._path, self._title, self._html = path, title, html
    def get_path(self): return self._path
    def get_title(self): return self._title
    def get_mimetype(self): return "text/html"
    def get_contentprovider(self): return StringProvider(self._html)
    def get_hints(self): return {Hint.FRONTARTICLE: True}

@pytest.fixture(scope="session")
def tiny_zim(tmp_path_factory):
    path = tmp_path_factory.mktemp("zim") / "tiny.zim"
    with Creator(str(path)).config_indexing(True, "eng") as c:
        c.add_item(_Article(
            "q1", "How to read a file in Python",
            "<html><body>Use the with open() context manager to read files safely "
            "so the file handle is always closed.</body></html>"))
        c.add_item(_Article(
            "q2", "List comprehension in Python",
            "<html><body>A list comprehension builds a list from an iterable "
            "in a single expression.</body></html>"))
        c.set_mainpath("q1")
    return str(path)
```

`retrieval-service/tests/test_zim_search.py`:
```python
from app.zim_search import ZimSearch

def test_search_finds_relevant_article(tiny_zim):
    zs = ZimSearch(tiny_zim)
    hits = zs.search("read file open", k=3)
    assert len(hits) >= 1
    assert any("read a file" in h.title.lower() for h in hits)

def test_search_empty_query_returns_empty(tiny_zim):
    assert ZimSearch(tiny_zim).search("", k=3) == []

def test_get_content_returns_html(tiny_zim):
    zs = ZimSearch(tiny_zim)
    hit = zs.search("read file open", k=1)[0]
    content = zs.get_content(hit.path)
    assert "with open()" in content

def test_get_content_bad_path_returns_empty(tiny_zim):
    assert ZimSearch(tiny_zim).get_content("nonexistent/path") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_zim_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.zim_search'`.

- [ ] **Step 3: Write minimal implementation**

`retrieval-service/app/zim_search.py`:
```python
from dataclasses import dataclass
from libzim.reader import Archive
from libzim.search import Query, Searcher

@dataclass
class SearchHit:
    path: str
    title: str

class ZimSearch:
    def __init__(self, zim_path: str):
        self._zim = Archive(zim_path)

    def search(self, query: str, k: int) -> list[SearchHit]:
        if not query.strip():
            return []
        q = Query().set_query(query)
        search = Searcher(self._zim).search(q)
        n = min(k, search.getEstimatedMatches())
        if n <= 0:
            return []
        hits: list[SearchHit] = []
        for path in search.getResults(0, n):
            try:
                entry = self._zim.get_entry_by_path(path)
                hits.append(SearchHit(path=path, title=entry.title))
            except Exception:
                continue
        return hits

    def get_content(self, path: str) -> str:
        try:
            item = self._zim.get_entry_by_path(path).get_item()
            return bytes(item.content).decode("utf-8", errors="ignore")
        except Exception:
            return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_zim_search.py -v`
Expected: PASS (4 testes). Se a API do libzim divergir (versão), ajuste contra a doc oficial `python-libzim.readthedocs.io` — os testes são a validação.

- [ ] **Step 5: Commit**

```bash
git add retrieval-service/app/zim_search.py retrieval-service/tests/conftest.py retrieval-service/tests/test_zim_search.py
git commit -m "feat(retrieval): zim full-text search via python-libzim"
```

---

### Task 4: Endpoint `/retrieve` (busca + snippet → JSON)

**Files:**
- Modify: `retrieval-service/app/main.py` (adiciona `/retrieve` + carga preguiçosa do `ZimSearch`)
- Create: `retrieval-service/app/retrieve.py`
- Test: `retrieval-service/tests/test_retrieve.py`

**Interfaces:**
- Consumes: `ZimSearch`/`SearchHit` (Task 3), `extract_snippet`/`strip_html` (Task 2).
- Produces:
  - `app.retrieve.build_results(zs: ZimSearch, query: str, k: int) -> list[dict]` — orquestra busca + snippet → `[{title, url, snippet}]`.
  - `GET /retrieve?q=&k=` no FastAPI usando `build_results`.

- [ ] **Step 1: Write the failing test**

`retrieval-service/tests/test_retrieve.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_retrieve.py -v`
Expected: FAIL — `app.retrieve` não existe / `_get_search` não existe.

- [ ] **Step 3: Write the orchestration module**

`retrieval-service/app/retrieve.py`:
```python
from app.zim_search import ZimSearch
from app.snippet import strip_html, extract_snippet

def build_results(zs: ZimSearch, query: str, k: int) -> list[dict]:
    results = []
    for hit in zs.search(query, k):
        text = strip_html(zs.get_content(hit.path))
        results.append({
            "title": hit.title,
            "url": hit.path,
            "snippet": extract_snippet(text, query),
        })
    return results
```

- [ ] **Step 4: Wire the endpoint in main.py**

Substitua `retrieval-service/app/main.py` por:
```python
import os
from fastapi import FastAPI, Query
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: PASS (todos: health + snippet + zim_search + retrieve).

- [ ] **Step 6: Commit**

```bash
git add retrieval-service/app/main.py retrieval-service/app/retrieve.py retrieval-service/tests/test_retrieve.py
git commit -m "feat(retrieval): /retrieve endpoint (search + snippet -> JSON)"
```

---

### Task 5: Script de execução + README + smoke test no `.zim` real

**Files:**
- Create: `retrieval-service/serve.ps1`
- Create: `retrieval-service/README.md`

**Interfaces:**
- Consumes: tudo das tarefas anteriores.
- Produces: forma de subir o serviço no servidor e validar contra o `.zim` real.

- [ ] **Step 1: Create the serve script**

`retrieval-service/serve.ps1`:
```powershell
# Sobe o serviço de retrieval. Defina PROFESSOR_ZIM_PATH se o .zim não estiver no default.
param([int]$Port = 8765)
$env:PROFESSOR_ZIM_PATH = $env:PROFESSOR_ZIM_PATH ?? "C:\acervo-llm\kiwix\stackoverflow.com_en_all_2023-11.zim"
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port $Port
```

- [ ] **Step 2: Create the README**

`retrieval-service/README.md`:
```markdown
# Professor — Retrieval Service (StackOverflow offline)

Serviço HTTP que busca no `.zim` do StackOverflow e devolve JSON para a extensão.

## Rodar
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
$env:PROFESSOR_ZIM_PATH = "C:\acervo-llm\kiwix\stackoverflow.com_en_all_2023-11.zim"
.\serve.ps1            # http://0.0.0.0:8765
```

## API
- `GET /health` → `{"status":"ok","zim_loaded":true}`
- `GET /retrieve?q=python+read+file&k=3` → `[{"title","url","snippet"}]`

## Testes
```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```
```

- [ ] **Step 3: Manual smoke test contra o `.zim` real (no servidor)**

Pré-requisito: rodar no servidor (Francesca), onde está o `.zim` de 80GB.
1. `.\serve.ps1`
2. Em outro terminal:
   ```powershell
   curl "http://localhost:8765/health"
   curl "http://localhost:8765/retrieve?q=python%20read%20file%20with%20open&k=3"
   ```
Expected: `/health` mostra `zim_loaded: true`; `/retrieve` devolve 1–3 itens com `title`/`url`/`snippet` reais do StackOverflow. (A 1ª query pode demorar enquanto o índice carrega.)

- [ ] **Step 4: Commit**

```bash
git add retrieval-service/serve.ps1 retrieval-service/README.md
git commit -m "chore(retrieval): serve script + README + smoke test"
```

---

## Notas de execução

- **Onde desenvolver vs rodar:** os testes (Tasks 1-4) rodam em qualquer máquina (usam o `.zim` de fixture minúsculo criado em memória). O smoke test (Task 5) precisa do servidor com o `.zim` real.
- **Deploy 24/7 (fora do escopo deste plano, anotar para depois):** transformar em serviço Windows (NSSM, como o ankivet) apontando pro `serve.ps1`, na porta 8765 do servidor, alcançável por Tailscale.
- **Próximo plano (Plano B):** integração na extensão — queryExtractor (qwen2.5-coder:1.5b), retrievalClient (HTTP a este serviço), grounded prompt + `source`, intenção, outline, panorama, painel em duas seções.
- **Risco conhecido:** a API exata do `python-libzim` (Creator/Searcher) pode variar por versão; os testes de fixture são a rede de segurança — se a versão instalada divergir, ajustar contra `python-libzim.readthedocs.io` mantendo as asserções dos testes.
