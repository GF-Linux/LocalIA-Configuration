# Fine-tune Fatia B1 — Régua de Avaliação Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a régua que mede se um modelo do Professor ficou melhor — 4 trilhas (validade de formato, qualidade pedagógica via Claude-juiz, A/B cego vs base, regressão de código HumanEval) — produzindo um veredito de promoção PROMOVER/NÃO.

**Architecture:** Pacote novo `eval/` espelhando o `fine-tune/`: lógica pura testável com pytest (probes, rubric, abtest, score, e a lógica de parse/contagem das peças de glue) + glue fina que fala com Ollama (local) e Claude (API). Reusa de `fine-tune/ftlib` o contrato de runtime (`is_valid_hint`, `TUTOR_SYSTEM`, `extract_json`) para medir exatamente o que o Professor faz. As partes de glue extraem a lógica testável para funções puras + injeção de dependência (mesmo padrão do `smoke_eval.score(records, asker)` da Fatia A); a execução real é validada por E2E manual.

**Tech Stack:** Python 3.12, pytest, `anthropic` (SDK oficial, juiz), `datasets` (HumanEval via `openai_humaneval`), Ollama (HTTP via `urllib`).

## Global Constraints

- 4 trilhas: **T0 formato** (reusa `is_valid_hint`/`extract_json`), **T1 qualidade pedagógica** (LLM-judge, 5 critérios 1-5), **T2 A/B cego vs base**, **T3 regressão de código** (HumanEval subset fixo).
- **Juiz = Claude via API**, modelo **`claude-opus-4-8`** (string exata; sem sufixo de data). SDK oficial `anthropic` (`from anthropic import Anthropic`).
- **NÃO** passar `temperature`, `top_p` nem `top_k` nas chamadas ao Claude — são removidos no Opus 4.8 e retornam **400**. Determinismo vem da rubrica explícita + parsing tolerante, não de `temperature`.
- **Chave da API**: lida de `os.environ["ANTHROPIC_API_KEY"]` (o SDK lê sozinho via `Anthropic()`). **Nunca** hardcodar a chave em código, teste, commit ou doc. Falhar com erro claro se ausente.
- Probe set curado **independente** dos dados de treino (`eval/data/probes.jsonl`, versionado). HumanEval subset fixo em `eval/data/humaneval_subset.txt`.
- Geração de dicas e de código via **Ollama local** (`http://localhost:11434`), HTTP com `urllib` (mesmo padrão do `fine-tune/ftlib/smoke_eval.py`). Regressão de código gera **sem** o system de tutor (modo code-completer).
- Gate de decisão **conjunto**: PROMOVER só se G0 ∧ G1 ∧ G2 ∧ G3 (limiares na Task 5).
- Pure modules testados com pytest (sem rede/GPU). Glue validado por E2E manual. Rodar `python -m pytest` de dentro de `eval/`.
- A régua **mede e recomenda**; **não** troca `professor.model` em produção (isso é a Fatia B3).

---

### Task 1: Scaffold do `eval/` + reuso do contrato de runtime

**Files:**
- Create: `eval/requirements.txt`
- Create: `eval/.gitignore`
- Create: `eval/README.md`
- Create: `eval/evallib/__init__.py`
- Create: `eval/evallib/contract.py`
- Create: `eval/tests/__init__.py`
- Test: `eval/tests/test_contract.py`

**Interfaces:**
- Consumes: `fine-tune/ftlib` (`is_valid_hint`, `TUTOR_SYSTEM`, `extract_json`).
- Produces:
  - `evallib.contract.is_valid_hint`, `evallib.contract.TUTOR_SYSTEM`, `evallib.contract.extract_json` — reexportados do `ftlib` da Fatia A (fonte única de verdade do contrato de runtime).

- [ ] **Step 1: Write the failing test**

`eval/tests/test_contract.py`:
```python
from evallib.contract import is_valid_hint, TUTOR_SYSTEM, extract_json

def test_reexports_is_valid_hint():
    assert is_valid_hint({"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"})
    assert not is_valid_hint({"comment": "c"})

def test_reexports_tutor_system_pt_json():
    s = TUTOR_SYSTEM.lower()
    assert "json" in s and "portugu" in s

def test_reexports_extract_json_tolerates_junk():
    assert extract_json('lixo {"a": 1} fim') == {"a": 1}
    assert extract_json("sem json") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (de `eval/`): `python -m pytest tests/test_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evallib.contract'`.

- [ ] **Step 3: Create project files**

`eval/requirements.txt`:
```
anthropic==0.69.0
datasets==2.20.0
pytest==8.2.0
```

`eval/.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
reports/
hf_cache/
```

`eval/evallib/__init__.py`: (vazio)
`eval/tests/__init__.py`: (vazio)

`eval/evallib/contract.py`:
```python
"""Reexporta o contrato de runtime do Professor a partir do pacote da Fatia A
(`fine-tune/ftlib`). Fonte única de verdade: a régua mede exatamente o que o
runtime produz. O diretório `fine-tune` tem hífen (não é importável como
pacote), então o adicionamos ao sys.path e importamos o pacote `ftlib`."""
import os
import sys

_FT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fine-tune"))
if _FT not in sys.path:
    sys.path.insert(0, _FT)

from ftlib.schema import is_valid_hint  # noqa: E402
from ftlib.format_chatml import TUTOR_SYSTEM  # noqa: E402
from ftlib.smoke_eval import extract_json  # noqa: E402

__all__ = ["is_valid_hint", "TUTOR_SYSTEM", "extract_json"]
```

`eval/README.md`:
```markdown
# Professor — Régua de avaliação (Fatia B1)

Mede se um modelo do Professor ficou melhor, em 4 trilhas:
formato (JSON), qualidade pedagógica (Claude-juiz), A/B cego vs base, regressão de código (HumanEval).

## Ambiente
`pip install -r requirements.txt`
Juiz: exige a variável de ambiente `ANTHROPIC_API_KEY` (NÃO commitar a chave).
Geração: Ollama local em `http://localhost:11434` com os modelos a comparar.

## Pipeline
    python run_eval.py --models professor-ft qwen2.5-coder:14b
Gera um relatório lado a lado das 4 trilhas + veredito (PROMOVER / NÃO PROMOVER).
Rode trilhas isoladas com flags (ver `python run_eval.py --help`) para não gastar API.
```

- [ ] **Step 4: Install deps and run test to verify it passes**

Run (de `eval/`): `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python -m pytest tests/test_contract.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add eval/
git commit -m "feat(eval): scaffold eval dir + reuse runtime contract from ftlib"
```

---

### Task 2: Probe set curado + loader validado

**Files:**
- Create: `eval/evallib/probes.py`
- Create: `eval/data/probes.jsonl`
- Test: `eval/tests/test_probes.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `evallib.probes.load_probes(path: str) -> list[dict]` — lê JSONL; cada linha = `{"id": str, "code": str, "lang": str, "teaching_point": str, "should_skip": bool}`; valida tipos e não-vazio (exceto `should_skip` que é bool); lança `ValueError` em linha inválida.
  - O arquivo `data/probes.jsonl` com **~40 probes** curados (ver Step 3).

- [ ] **Step 1: Write the failing test**

`eval/tests/test_probes.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_probes.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the loader and the curated probe file**

`eval/evallib/probes.py`:
```python
import json

_FIELDS_STR = ("id", "code", "lang", "teaching_point")

def load_probes(path: str) -> list[dict]:
    probes = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for k in _FIELDS_STR:
                if not (isinstance(row.get(k), str) and row[k].strip()):
                    raise ValueError(f"linha {i}: '{k}' ausente/vazio")
            if not isinstance(row.get("should_skip"), bool):
                raise ValueError(f"linha {i}: 'should_skip' deve ser bool")
            probes.append(row)
    return probes
```

`eval/data/probes.jsonl` — **fabricar ~40 probes curados** (uma linha JSON por probe), **independentes** do `seeds.jsonl` do treino. Schema por linha:
```json
{"id": "rec-open", "code": "f = open('dados.txt')\nconteudo = f.read()", "lang": "python", "teaching_point": "recurso não fechado; usar with", "should_skip": false}
```
Mais dois exemplos (um JS, um "deve calar"):
```json
{"id": "js-var-loop", "code": "for (var i = 0; i < fns.length; i++) {\n  fns[i] = function () { return i; };\n}", "lang": "javascript", "teaching_point": "closure capturando var em loop; usar let", "should_skip": false}
{"id": "skip-trivial-sum", "code": "total = a + b\nprint(total)", "lang": "python", "teaching_point": "código trivial e correto; nada a ensinar", "should_skip": true}
```
Diretrizes para os ~40:
- Variar tema (recursos não fechados, mutável como default, igualdade vs identidade, comparação com `is`, list comprehension, except genérico, f-string vs concat, etc.) e linguagem (maioria Python; alguns JS/TS).
- Incluir **~8 probes `should_skip: true`** (código trivial/correto) para medir seletividade.
- `teaching_point` é uma nota curta de referência (não vai pro modelo; ajuda na curadoria e na leitura do relatório).
- **Não reusar trechos do `fine-tune/data/seeds.jsonl`** — o probe set é o teste, deve ser disjunto do treino.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_probes.py -v`
Expected: PASS (5 testes; o último confirma ≥30 probes reais com mistura de skip/ensinável).

- [ ] **Step 5: Commit**

```bash
git add eval/evallib/probes.py eval/tests/test_probes.py eval/data/probes.jsonl
git commit -m "feat(eval): curated independent probe set + validated loader"
```

---

### Task 3: Rubrica pedagógica (critérios + prompt + parse + trilha T1)

**Files:**
- Create: `eval/evallib/rubric.py`
- Test: `eval/tests/test_rubric.py`

**Interfaces:**
- Consumes: nada (recebe `ask` injetado nas funções de orquestração).
- Produces:
  - `evallib.rubric.RUBRIC_CRITERIA: tuple[str, ...]` = `("socratic", "why", "concision", "relevance", "correctness")`.
  - `evallib.rubric.build_judge_prompt(probe: dict, hint_text: str) -> str` — monta o texto enviado ao juiz (trecho + dica + rubrica; pede JSON).
  - `evallib.rubric.parse_verdict(raw: str) -> dict | None` — extrai `{"scores": {5 chaves int 1-5}, "rationale": str}`; `None` se inválido.
  - `evallib.rubric.score_quality(items: list[tuple[dict, str]], ask) -> dict` — para cada `(probe, hint_text)`, chama `ask(prompt)->str`, parseia; devolve `{"n": int, "valid": int, "means": {criterio: float}, "overall": float}` (médias só sobre vereditos válidos). `ask` injetado → testável com mock.

- [ ] **Step 1: Write the failing test**

`eval/tests/test_rubric.py`:
```python
import json
from evallib.rubric import RUBRIC_CRITERIA, build_judge_prompt, parse_verdict, score_quality

def test_criteria_constant():
    assert RUBRIC_CRITERIA == ("socratic", "why", "concision", "relevance", "correctness")

def test_build_prompt_includes_code_and_hint_and_json():
    probe = {"code": "open('f')", "lang": "python"}
    p = build_judge_prompt(probe, '{"comment":"c"}')
    assert "open('f')" in p
    assert '{"comment":"c"}' in p
    assert "json" in p.lower()
    for c in RUBRIC_CRITERIA:
        assert c in p

def test_parse_verdict_ok():
    raw = 'lixo {"scores": {"socratic":5,"why":4,"concision":3,"relevance":5,"correctness":4}, "rationale":"r"} fim'
    v = parse_verdict(raw)
    assert v["scores"]["socratic"] == 5 and v["rationale"] == "r"

def test_parse_verdict_rejects_out_of_range():
    raw = '{"scores": {"socratic":6,"why":4,"concision":3,"relevance":5,"correctness":4}, "rationale":"r"}'
    assert parse_verdict(raw) is None

def test_parse_verdict_rejects_missing_key():
    raw = '{"scores": {"socratic":5,"why":4,"concision":3,"relevance":5}, "rationale":"r"}'
    assert parse_verdict(raw) is None

def test_parse_verdict_rejects_garbage():
    assert parse_verdict("não é json") is None

def test_score_quality_aggregates_valid_only():
    items = [({"code": "a", "lang": "python"}, "h1"),
             ({"code": "b", "lang": "python"}, "h2")]
    replies = iter([
        '{"scores": {"socratic":4,"why":4,"concision":4,"relevance":4,"correctness":4}, "rationale":"r"}',
        'lixo inválido',
    ])
    out = score_quality(items, lambda prompt: next(replies))
    assert out["n"] == 2 and out["valid"] == 1
    assert out["means"]["socratic"] == 4.0
    assert out["overall"] == 4.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rubric.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the module**

`eval/evallib/rubric.py`:
```python
from evallib.contract import extract_json

RUBRIC_CRITERIA = ("socratic", "why", "concision", "relevance", "correctness")

_RUBRIC_TEXT = (
    "Avalie a DICA de um tutor de programação sobre o TRECHO do aluno, em 5 critérios, "
    "nota inteira de 1 (ruim) a 5 (ótimo):\n"
    "- socratic: dá um empurrão sem entregar a solução pronta (5) vs reescreve tudo (1).\n"
    "- why: explica o porquê/conceito (5) vs só aponta o erro (1).\n"
    "- concision: conciso e direto (5) vs prolixo (1).\n"
    "- relevance: específico ao trecho (5) vs genérico/fora de contexto (1).\n"
    "- correctness: tecnicamente correto (5) vs errado/enganoso (1).\n"
    'Responda SOMENTE em JSON: {"scores": {"socratic":n,"why":n,"concision":n,'
    '"relevance":n,"correctness":n}, "rationale": "..."}.'
)

def build_judge_prompt(probe: dict, hint_text: str) -> str:
    return (
        f"{_RUBRIC_TEXT}\n\n"
        f"Linguagem: {probe['lang']}\n"
        f"TRECHO:\n{probe['code']}\n\n"
        f"DICA DO MODELO:\n{hint_text}"
    )

def parse_verdict(raw: str):
    obj = extract_json(raw or "")
    if not isinstance(obj, dict):
        return None
    scores = obj.get("scores")
    if not isinstance(scores, dict):
        return None
    for c in RUBRIC_CRITERIA:
        v = scores.get(c)
        if not (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5):
            return None
    if not isinstance(obj.get("rationale"), str):
        return None
    return {"scores": {c: scores[c] for c in RUBRIC_CRITERIA}, "rationale": obj["rationale"]}

def score_quality(items, ask) -> dict:
    verdicts = []
    for probe, hint_text in items:
        v = parse_verdict(ask(build_judge_prompt(probe, hint_text)))
        if v is not None:
            verdicts.append(v)
    n = len(items)
    valid = len(verdicts)
    means = {}
    for c in RUBRIC_CRITERIA:
        means[c] = (sum(v["scores"][c] for v in verdicts) / valid) if valid else 0.0
    overall = (sum(means[c] for c in RUBRIC_CRITERIA) / len(RUBRIC_CRITERIA)) if valid else 0.0
    return {"n": n, "valid": valid, "means": means, "overall": overall}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rubric.py -v`
Expected: PASS (7 testes).

- [ ] **Step 5: Commit**

```bash
git add eval/evallib/rubric.py eval/tests/test_rubric.py
git commit -m "feat(eval): pedagogical rubric (criteria, prompt, parse, T1 aggregator)"
```

---

### Task 4: A/B cego vs base (par cego + parse + tally)

**Files:**
- Create: `eval/evallib/abtest.py`
- Test: `eval/tests/test_abtest.py`

**Interfaces:**
- Consumes: nada (recebe `ask` injetado).
- Produces:
  - `evallib.abtest.build_pair(probe, hint_ft, hint_base, rng) -> tuple[str, dict]` — monta o prompt cego (rótulos A/B, ordem randomizada via `rng`) e o `mapping` `{"A": "ft"|"base", "B": ...}`.
  - `evallib.abtest.parse_choice(raw: str) -> str | None` — extrai `"A"`, `"B"` ou `"tie"` do JSON `{"winner": "A"|"B"|"tie"}`; `None` se inválido.
  - `evallib.abtest.compare(probes, hints_ft, hints_base, ask, seed) -> dict` — para cada probe, monta par cego, pergunta ao `ask`, de-anonimiza; devolve `{"n": int, "valid": int, "ft_wins": int, "base_wins": int, "ties": int}`. Determinístico com `seed`. `ask` injetado → testável.

- [ ] **Step 1: Write the failing test**

`eval/tests/test_abtest.py`:
```python
import random
from evallib.abtest import build_pair, parse_choice, compare

def test_build_pair_is_blind_and_maps_back():
    probe = {"code": "x=1", "lang": "python"}
    prompt, mapping = build_pair(probe, "DICA_FT", "DICA_BASE", random.Random(0))
    assert "DICA_FT" in prompt and "DICA_BASE" in prompt
    assert "x=1" in prompt
    assert set(mapping.keys()) == {"A", "B"}
    assert set(mapping.values()) == {"ft", "base"}
    # cego: o prompt usa rótulos A/B, não revela qual modelo é qual
    assert "ft" not in prompt and "base" not in prompt

def test_build_pair_deterministic_with_same_rng():
    probe = {"code": "x", "lang": "python"}
    a = build_pair(probe, "F", "B", random.Random(42))[1]
    b = build_pair(probe, "F", "B", random.Random(42))[1]
    assert a == b

def test_parse_choice():
    assert parse_choice('{"winner": "A"}') == "A"
    assert parse_choice('lixo {"winner":"tie"} fim') == "tie"
    assert parse_choice('{"winner": "C"}') is None
    assert parse_choice("nada") is None

def test_compare_tally_deanonymizes():
    probes = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"},
              {"code": "c", "lang": "python"}]
    hints_ft = ["ft0", "ft1", "ft2"]
    hints_base = ["b0", "b1", "b2"]
    # juiz sempre escolhe o rótulo que contém o texto "ft"
    def ask(prompt):
        # encontra qual rótulo (A/B) precede o texto que tem 'ft'
        ia, ib = prompt.index("Resposta A"), prompt.index("Resposta B")
        a_text = prompt[ia:ib]
        return '{"winner": "A"}' if "ft" in a_text else '{"winner": "B"}'
    out = compare(probes, hints_ft, hints_base, ask, seed=1)
    assert out["n"] == 3 and out["valid"] == 3
    assert out["ft_wins"] == 3 and out["base_wins"] == 0 and out["ties"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_abtest.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the module**

`eval/evallib/abtest.py`:
```python
import random
from evallib.contract import extract_json

_INSTR = (
    "Duas dicas de tutor para o mesmo trecho de código. Escolha a MELHOR como ensino "
    "(mais didática, ensina o porquê sem entregar a solução, concisa e correta). "
    'Responda SOMENTE em JSON: {"winner": "A"} ou {"winner": "B"} ou {"winner": "tie"}.'
)

def build_pair(probe: dict, hint_ft: str, hint_base: str, rng: random.Random):
    # randomiza qual modelo recebe o rótulo A
    if rng.random() < 0.5:
        mapping = {"A": "ft", "B": "base"}
        a_text, b_text = hint_ft, hint_base
    else:
        mapping = {"A": "base", "B": "ft"}
        a_text, b_text = hint_base, hint_ft
    prompt = (
        f"{_INSTR}\n\n"
        f"Linguagem: {probe['lang']}\n"
        f"TRECHO:\n{probe['code']}\n\n"
        f"Resposta A:\n{a_text}\n\n"
        f"Resposta B:\n{b_text}"
    )
    return prompt, mapping

def parse_choice(raw: str):
    obj = extract_json(raw or "")
    if not isinstance(obj, dict):
        return None
    w = obj.get("winner")
    return w if w in ("A", "B", "tie") else None

def compare(probes, hints_ft, hints_base, ask, seed: int) -> dict:
    rng = random.Random(seed)
    ft_wins = base_wins = ties = valid = 0
    for probe, hf, hb in zip(probes, hints_ft, hints_base):
        prompt, mapping = build_pair(probe, hf, hb, rng)
        choice = parse_choice(ask(prompt))
        if choice is None:
            continue
        valid += 1
        if choice == "tie":
            ties += 1
        elif mapping[choice] == "ft":
            ft_wins += 1
        else:
            base_wins += 1
    return {"n": len(probes), "valid": valid,
            "ft_wins": ft_wins, "base_wins": base_wins, "ties": ties}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_abtest.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add eval/evallib/abtest.py eval/tests/test_abtest.py
git commit -m "feat(eval): blind A/B comparison (pair, parse, de-anonymized tally)"
```

---

### Task 5: Score — agregação das 4 trilhas + gate de decisão

**Files:**
- Create: `eval/evallib/score.py`
- Test: `eval/tests/test_score.py`

**Interfaces:**
- Consumes: dicionários de resultado das Tasks 3 e 4 (e contagens das Tasks 7/8).
- Produces:
  - `evallib.score.GATE_THRESHOLDS: dict` — `{"format_min": 0.95, "code_eps": 0.05}` (configurável).
  - `evallib.score.compute_gates(results: dict) -> dict` — recebe um dict com as 4 trilhas para o modelo ft + a baseline; devolve `{"G0": bool, "G1": bool, "G2": bool, "G3": bool}`.
  - `evallib.score.verdict(gates: dict) -> str` — `"PROMOVER"` se todos True, senão `"NAO_PROMOVER"`.
  - `evallib.score.format_report(results: dict, gates: dict) -> str` — resumo legível (texto).

  Forma de `results` esperada:
  ```python
  {
    "format": {"ft": 0.97, "base": 0.99},          # frac JSON válido (T0)
    "quality": {"overall_ft": 4.1, "overall_base": 3.6},  # média global rubrica (T1)
    "ab": {"ft_wins": 22, "base_wins": 10, "ties": 8},    # (T2)
    "code": {"ft": 0.71, "base": 0.74},            # pass@1 (T3)
    "selectivity": {"correct": 6, "total": 8},     # casos "deve calar" (sub-T0)
  }
  ```

- [ ] **Step 1: Write the failing test**

`eval/tests/test_score.py`:
```python
from evallib.score import compute_gates, verdict, GATE_THRESHOLDS

_PASS = {
    "format": {"ft": 0.97, "base": 0.99},
    "quality": {"overall_ft": 4.1, "overall_base": 3.6},
    "ab": {"ft_wins": 22, "base_wins": 10, "ties": 8},
    "code": {"ft": 0.71, "base": 0.74},
    "selectivity": {"correct": 6, "total": 8},
}

def test_all_gates_pass_promotes():
    g = compute_gates(_PASS)
    assert g == {"G0": True, "G1": True, "G2": True, "G3": True}
    assert verdict(g) == "PROMOVER"

def test_g0_format_below_threshold_fails():
    r = {**_PASS, "format": {"ft": 0.90, "base": 0.99}}
    assert compute_gates(r)["G0"] is False
    assert verdict(compute_gates(r)) == "NAO_PROMOVER"

def test_g1_fails_when_ab_not_positive():
    r = {**_PASS, "ab": {"ft_wins": 10, "base_wins": 22, "ties": 8}}
    assert compute_gates(r)["G1"] is False

def test_g1_fails_when_rubric_below_base():
    r = {**_PASS, "quality": {"overall_ft": 3.4, "overall_base": 3.6}}
    assert compute_gates(r)["G1"] is False

def test_g2_code_regression_within_epsilon_passes():
    # ft 0.70 vs base 0.74 → diff 0.04 <= eps 0.05 → passa
    r = {**_PASS, "code": {"ft": 0.70, "base": 0.74}}
    assert compute_gates(r)["G2"] is True

def test_g2_code_regression_beyond_epsilon_fails():
    r = {**_PASS, "code": {"ft": 0.60, "base": 0.74}}
    assert compute_gates(r)["G2"] is False

def test_g3_selectivity_below_half_fails():
    r = {**_PASS, "selectivity": {"correct": 3, "total": 8}}
    assert compute_gates(r)["G3"] is False

def test_thresholds_constant():
    assert GATE_THRESHOLDS["format_min"] == 0.95
    assert GATE_THRESHOLDS["code_eps"] == 0.05
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_score.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the module**

`eval/evallib/score.py`:
```python
GATE_THRESHOLDS = {"format_min": 0.95, "code_eps": 0.05}

def compute_gates(results: dict) -> dict:
    fmt = results["format"]
    qual = results["quality"]
    ab = results["ab"]
    code = results["code"]
    sel = results["selectivity"]

    g0 = fmt["ft"] >= GATE_THRESHOLDS["format_min"]
    g1 = (ab["ft_wins"] > ab["base_wins"]) and (qual["overall_ft"] >= qual["overall_base"])
    g2 = code["ft"] >= code["base"] - GATE_THRESHOLDS["code_eps"]
    g3 = sel["total"] > 0 and (sel["correct"] / sel["total"]) >= 0.5
    return {"G0": g0, "G1": g1, "G2": g2, "G3": g3}

def verdict(gates: dict) -> str:
    return "PROMOVER" if all(gates.values()) else "NAO_PROMOVER"

def format_report(results: dict, gates: dict) -> str:
    fmt, qual, ab = results["format"], results["quality"], results["ab"]
    code, sel = results["code"], results["selectivity"]
    lines = [
        "=== Régua do Professor (B1) ===",
        f"T0 formato (JSON válido):  ft={fmt['ft']:.2f}  base={fmt['base']:.2f}   [G0={gates['G0']}]",
        f"T1 rubrica (média global): ft={qual['overall_ft']:.2f}  base={qual['overall_base']:.2f}",
        f"T2 A/B cego:  ft={ab['ft_wins']}  base={ab['base_wins']}  empates={ab['ties']}   [G1={gates['G1']}]",
        f"T3 código pass@1:  ft={code['ft']:.2f}  base={code['base']:.2f}   [G2={gates['G2']}]",
        f"Seletividade (deve calar): {sel['correct']}/{sel['total']}   [G3={gates['G3']}]",
        f">>> VEREDITO: {verdict(gates)}",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_score.py -v`
Expected: PASS (8 testes).

- [ ] **Step 5: Commit**

```bash
git add eval/evallib/score.py eval/tests/test_score.py
git commit -m "feat(eval): 4-track aggregation + 4-gate promotion verdict"
```

---

### Task 6: Juiz Claude (glue) + cliente da API

**Files:**
- Create: `eval/evallib/judge.py`
- Test: `eval/tests/test_judge.py`

**Interfaces:**
- Consumes: `ANTHROPIC_API_KEY` (env), SDK `anthropic`.
- Produces:
  - `evallib.judge.JUDGE_MODEL: str` = `"claude-opus-4-8"`.
  - `evallib.judge.make_claude_ask(model: str = JUDGE_MODEL) -> Callable[[str], str]` — devolve `ask(prompt)->str` que chama o Claude e retorna o texto. Cria o cliente `Anthropic()` (lê a chave do env). Lança `RuntimeError` claro se `ANTHROPIC_API_KEY` não estiver setada.
  - `evallib.judge.extract_text(resp) -> str` — função pura que extrai o texto concatenado dos blocos `type == "text"` de uma resposta do SDK (testável com um objeto fake).

- [ ] **Step 1: Write the failing test (lógica pura, sem rede)**

`eval/tests/test_judge.py`:
```python
import pytest
from evallib.judge import extract_text, make_claude_ask, JUDGE_MODEL

class _Block:
    def __init__(self, type, text=""):
        self.type = type
        self.text = text

class _Resp:
    def __init__(self, blocks):
        self.content = blocks

def test_judge_model_is_opus_4_8():
    assert JUDGE_MODEL == "claude-opus-4-8"

def test_extract_text_concatenates_text_blocks_only():
    resp = _Resp([_Block("thinking", "ignora"), _Block("text", "ola "), _Block("text", "mundo")])
    assert extract_text(resp) == "ola mundo"

def test_extract_text_empty_when_no_text_blocks():
    assert extract_text(_Resp([_Block("thinking", "x")])) == ""

def test_make_claude_ask_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        make_claude_ask()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_judge.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the module**

`eval/evallib/judge.py`:
```python
"""Juiz via Claude API (SDK oficial). Modelo: claude-opus-4-8.
NÃO passar temperature/top_p/top_k (removidos no Opus 4.8 -> 400).
A chave vem de ANTHROPIC_API_KEY (o SDK a lê sozinho); nunca hardcodar."""
import os

JUDGE_MODEL = "claude-opus-4-8"

def extract_text(resp) -> str:
    parts = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts)

def make_claude_ask(model: str = JUDGE_MODEL):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY não definida. Exporte sua chave antes de rodar o juiz "
            "(NÃO commitar a chave)."
        )
    from anthropic import Anthropic
    client = Anthropic()  # lê ANTHROPIC_API_KEY do ambiente

    def ask(prompt: str) -> str:
        # sem temperature/top_p/top_k (Opus 4.8 rejeita). max_tokens enxuto: a saída é JSON curto.
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return extract_text(resp)

    return ask
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_judge.py -v`
Expected: PASS (4 testes). (A chamada real ao Claude NÃO é unit-testada — é exercida no E2E da Task 9.)

- [ ] **Step 5: Smoke-test manual da API (1 chamada; precisa da chave)**

Pré: `export ANTHROPIC_API_KEY=...` (no WSL/terminal; não commitar).
Run (de `eval/`):
```bash
python -c "from evallib.judge import make_claude_ask; print(make_claude_ask()('Responda SOMENTE em JSON: {\"ok\": true}'))"
```
Expected: imprime algo contendo `{"ok": true}`. Confirma chave + SDK + modelo `claude-opus-4-8`.

- [ ] **Step 6: Commit**

```bash
git add eval/evallib/judge.py eval/tests/test_judge.py
git commit -m "feat(eval): Claude judge client (opus-4-8, env key, pure text extractor)"
```

---

### Task 7: Runners — gera dicas via Ollama + trilha T0 (formato/seletividade)

**Files:**
- Create: `eval/evallib/runners.py`
- Test: `eval/tests/test_runners.py`

**Interfaces:**
- Consumes: `TUTOR_SYSTEM`, `is_valid_hint`, `extract_json` (contrato); `ask` injetado.
- Produces:
  - `evallib.runners.build_tutor_messages(probe: dict) -> list[dict]` — `[{role:system, TUTOR_SYSTEM}, {role:user, código}]` (espelha o runtime).
  - `evallib.runners.make_ollama_ask(model: str, url: str = "http://localhost:11434") -> Callable[[list[dict]], str]` — devolve `ask(messages)->str` (HTTP `/api/chat`, `stream=False`), padrão do `smoke_eval`.
  - `evallib.runners.generate_hints(probes, ask) -> list[str]` — para cada probe, monta as mensagens e chama `ask`; devolve a lista de textos crus.
  - `evallib.runners.score_format(probes, hints) -> dict` — `{"frac": float, "valid": int, "total": int}` (T0, JSON válido).
  - `evallib.runners.score_selectivity(probes, hints) -> dict` — entre os `should_skip=true`, conta quantos o modelo corretamente calou (`extract_json(...)` com `skip is True`). `{"correct": int, "total": int}`.

- [ ] **Step 1: Write the failing test**

`eval/tests/test_runners.py`:
```python
from evallib.runners import (build_tutor_messages, generate_hints,
                             score_format, score_selectivity)
from evallib.contract import TUTOR_SYSTEM

def test_build_tutor_messages_mirrors_runtime():
    msgs = build_tutor_messages({"code": "open('f')", "lang": "python"})
    assert [m["role"] for m in msgs] == ["system", "user"]
    assert msgs[0]["content"] == TUTOR_SYSTEM
    assert "open('f')" in msgs[1]["content"]
    assert "python" in msgs[1]["content"]

def test_generate_hints_uses_ask_per_probe():
    probes = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"}]
    replies = iter(["h1", "h2"])
    out = generate_hints(probes, lambda messages: next(replies))
    assert out == ["h1", "h2"]

def test_score_format_counts_valid_json():
    probes = [{"code": "a", "lang": "python"}, {"code": "b", "lang": "python"}]
    hints = ['{"comment":"c","why":"w","nudge":"n","suggestion":"s"}', "lixo"]
    out = score_format(probes, hints)
    assert out == {"frac": 0.5, "valid": 1, "total": 2}

def test_score_selectivity_only_should_skip():
    probes = [
        {"code": "a", "lang": "python", "should_skip": True},
        {"code": "b", "lang": "python", "should_skip": True},
        {"code": "c", "lang": "python", "should_skip": False},
    ]
    hints = ['{"skip": true}', '{"comment":"c","why":"w","nudge":"n","suggestion":"s"}', "x"]
    out = score_selectivity(probes, hints)
    # 2 casos "deve calar"; só o 1º calou corretamente
    assert out == {"correct": 1, "total": 2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_runners.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the module**

`eval/evallib/runners.py`:
```python
import json
import urllib.request
from evallib.contract import TUTOR_SYSTEM, is_valid_hint, extract_json

def build_tutor_messages(probe: dict) -> list[dict]:
    user = f"Linguagem: {probe['lang']}\nCódigo:\n{probe['code']}"
    return [
        {"role": "system", "content": TUTOR_SYSTEM},
        {"role": "user", "content": user},
    ]

def make_ollama_ask(model: str, url: str = "http://localhost:11434"):
    def ask(messages: list[dict]) -> str:
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["message"]["content"]
    return ask

def generate_hints(probes, ask) -> list[str]:
    return [ask(build_tutor_messages(p)) for p in probes]

def score_format(probes, hints) -> dict:
    total = len(probes)
    valid = sum(1 for h in hints if is_valid_hint(extract_json(h or "")))
    return {"frac": (valid / total) if total else 0.0, "valid": valid, "total": total}

def score_selectivity(probes, hints) -> dict:
    correct = total = 0
    for p, h in zip(probes, hints):
        if not p.get("should_skip"):
            continue
        total += 1
        obj = extract_json(h or "")
        if isinstance(obj, dict) and obj.get("skip") is True:
            correct += 1
    return {"correct": correct, "total": total}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_runners.py -v`
Expected: PASS (4 testes). (A chamada real ao Ollama é exercida no E2E da Task 9.)

- [ ] **Step 5: Commit**

```bash
git add eval/evallib/runners.py eval/tests/test_runners.py
git commit -m "feat(eval): Ollama hint runner + format/selectivity (T0)"
```

---

### Task 8: Regressão de código — HumanEval subset + sandbox (T3)

**Files:**
- Create: `eval/evallib/codegen.py`
- Create: `eval/evallib/sandbox.py`
- Create: `eval/data/humaneval_subset.txt`
- Test: `eval/tests/test_codegen.py`

**Interfaces:**
- Consumes: dataset `openai_humaneval` (via `datasets`), Ollama (`ask` injetado), subprocesso.
- Produces:
  - `evallib.codegen.build_code_prompt(problem: dict) -> str` — prompt de completar código a partir de `problem["prompt"]` (assinatura + docstring), **sem** system de tutor.
  - `evallib.codegen.strip_code_fence(raw: str) -> str` — remove cercas ```` ```python ```` se presentes; devolve o corpo.
  - `evallib.codegen.make_ollama_code_ask(model, url) -> Callable[[str], str]` — `ask(prompt)->str` via `/api/generate` (texto puro, `stream=False`).
  - `evallib.codegen.load_subset_ids(path: str) -> list[str]` — lê os task_ids fixos.
  - `evallib.sandbox.run_one(problem: dict, completion: str, executor) -> bool` — monta `prompt + completion + "\n" + test + "\ncheck(" + entry_point + ")"`, chama `executor(program)->int` (returncode), devolve `rc == 0`. `executor` injetado → testável.
  - `evallib.sandbox.subprocess_executor(timeout: float) -> Callable[[str], int]` — roda `python -c <program>` em subprocesso com timeout; timeout/erro → returncode != 0.
  - `evallib.codegen.pass_at_1(problems, completions, executor) -> dict` — `{"passed": int, "total": int, "frac": float}`.

- [ ] **Step 1: Write the failing test**

`eval/tests/test_codegen.py`:
```python
from evallib.codegen import build_code_prompt, strip_code_fence, pass_at_1, load_subset_ids
from evallib.sandbox import run_one

def test_build_code_prompt_has_signature_no_tutor():
    p = build_code_prompt({"prompt": "def add(a, b):\n    \"\"\"soma\"\"\"\n"})
    assert "def add(a, b):" in p
    assert "professor" not in p.lower()  # não é o system de tutor

def test_strip_code_fence():
    assert strip_code_fence("```python\nx=1\n```") == "x=1"
    assert strip_code_fence("x=2") == "x=2"

def test_run_one_passes_for_correct_completion():
    problem = {
        "prompt": "def add(a, b):\n",
        "test": "def check(candidate):\n    assert candidate(2, 3) == 5\n",
        "entry_point": "add",
    }
    # executor finge rodar e devolve 0 (sucesso) — testa a montagem/contrato
    captured = {}
    def fake_exec(program):
        captured["program"] = program
        return 0
    assert run_one(problem, "    return a + b\n", fake_exec) is True
    assert "def add(a, b):" in captured["program"]
    assert "def check(candidate):" in captured["program"]
    assert "check(add)" in captured["program"]

def test_run_one_fails_when_executor_nonzero():
    problem = {"prompt": "def f():\n", "test": "def check(c):\n    pass\n", "entry_point": "f"}
    assert run_one(problem, "    return 1\n", lambda program: 1) is False

def test_pass_at_1_counts():
    problems = [{"prompt": "def f():\n", "test": "def check(c):\n    pass\n", "entry_point": "f"},
                {"prompt": "def g():\n", "test": "def check(c):\n    pass\n", "entry_point": "g"}]
    completions = ["    return 1\n", "    return 2\n"]
    rc = iter([0, 1])
    out = pass_at_1(problems, completions, lambda program: next(rc))
    assert out == {"passed": 1, "total": 2, "frac": 0.5}

def test_real_subset_file_loads():
    ids = load_subset_ids("data/humaneval_subset.txt")
    assert len(ids) >= 30
    assert all(i.startswith("HumanEval/") for i in ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_codegen.py -v`
Expected: FAIL — módulos não existem.

- [ ] **Step 3: Write the modules and the subset file**

`eval/evallib/codegen.py`:
```python
import json
import urllib.request

def build_code_prompt(problem: dict) -> str:
    return (
        "Complete a função abaixo. Responda SOMENTE com o corpo/código Python, "
        "sem explicações.\n\n" + problem["prompt"]
    )

def strip_code_fence(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.endswith("```"):
            s = s[: s.rfind("```")]
    return s.strip("\n")

def make_ollama_code_ask(model: str, url: str = "http://localhost:11434"):
    def ask(prompt: str) -> str:
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read()).get("response", "")
    return ask

def load_subset_ids(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]

def pass_at_1(problems, completions, executor) -> dict:
    from evallib.sandbox import run_one
    passed = sum(1 for p, c in zip(problems, completions) if run_one(p, c, executor))
    total = len(problems)
    return {"passed": passed, "total": total, "frac": (passed / total) if total else 0.0}
```

`eval/evallib/sandbox.py`:
```python
import subprocess

def run_one(problem: dict, completion: str, executor) -> bool:
    program = (
        problem["prompt"] + completion + "\n"
        + problem["test"] + "\n"
        + f"check({problem['entry_point']})\n"
    )
    return executor(program) == 0

def subprocess_executor(timeout: float):
    """Executa código gerado por LLM isolado, com timeout. ATENÇÃO: roda código
    arbitrário — usar só em máquina de dev confiável (WSL). timeout/erro -> rc!=0."""
    def execute(program: str) -> int:
        try:
            proc = subprocess.run(
                ["python", "-c", program],
                capture_output=True, timeout=timeout,
            )
            return proc.returncode
        except subprocess.TimeoutExpired:
            return 124
        except Exception:
            return 1
    return execute
```

`eval/data/humaneval_subset.txt` (subset fixo — os 35 primeiros problemas do HumanEval):
```
# HumanEval subset fixo para a régua de regressão (T3). 35 problemas.
HumanEval/0
HumanEval/1
HumanEval/2
HumanEval/3
HumanEval/4
HumanEval/5
HumanEval/6
HumanEval/7
HumanEval/8
HumanEval/9
HumanEval/10
HumanEval/11
HumanEval/12
HumanEval/13
HumanEval/14
HumanEval/15
HumanEval/16
HumanEval/17
HumanEval/18
HumanEval/19
HumanEval/20
HumanEval/21
HumanEval/22
HumanEval/23
HumanEval/24
HumanEval/25
HumanEval/26
HumanEval/27
HumanEval/28
HumanEval/29
HumanEval/30
HumanEval/31
HumanEval/32
HumanEval/33
HumanEval/34
```

> **Nota de fidelidade ao spec:** o spec (decisão #4) pede "HumanEval oficial, subset fixo". Acessamos os 164 problemas canônicos do HumanEval via o dataset `openai_humaneval` (HuggingFace — mesma família já usada na Fatia A com `datasets`) e fixamos o subset pelos `task_id` acima. A execução usa nosso próprio sandbox com timeout (Task, `subprocess_executor`), o que cumpre o "execução sandboxed com timeout" do design e evita o executor opt-in/gated do pacote `human-eval` — mesmos problemas, execução controlável.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_codegen.py -v`
Expected: PASS (6 testes). (Download do dataset e execução real são exercidos no E2E da Task 9.)

- [ ] **Step 5: Commit**

```bash
git add eval/evallib/codegen.py eval/evallib/sandbox.py eval/data/humaneval_subset.txt eval/tests/test_codegen.py
git commit -m "feat(eval): HumanEval-subset code regression (codegen + sandbox, T3)"
```

---

### Task 9: Orquestrador `run_eval.py` + E2E (baseline professor-ft vs base)

**Files:**
- Create: `eval/run_eval.py`
- Modify: `eval/README.md` (exemplo de uso real, se necessário)

**Interfaces:**
- Consumes: tudo das Tasks 2-8.
- Produces: relatório lado a lado das 4 trilhas + veredito, gravado em `reports/` (gitignored) e impresso.

**Nota:** sem unit test (é orquestração I/O — Ollama + Claude + dataset). A validação é o E2E manual rodar e produzir o relatório/baseline. As peças que ele chama já são todas testadas.

- [ ] **Step 1: Write the orchestrator**

`eval/run_eval.py`:
```python
"""Régua do Professor (B1). Roda as 4 trilhas para o modelo fine-tunado e o base,
e imprime o veredito de promoção. Trilhas caras (juiz/API) podem ser puladas com flags.

Pré-requisitos:
  - Ollama local com os modelos (ex.: professor-ft e qwen2.5-coder:14b).
  - ANTHROPIC_API_KEY no ambiente (para as trilhas de juiz/A-B). NÃO commitar a chave.

Uso:
  python run_eval.py --ft professor-ft --base qwen2.5-coder:14b
  python run_eval.py --ft professor-ft --base qwen2.5-coder:14b --no-judge  # só T0+T3 (sem API)
"""
import argparse
import json
import os
import sys

from evallib.probes import load_probes
from evallib.runners import make_ollama_ask, generate_hints, score_format, score_selectivity
from evallib.rubric import score_quality
from evallib.abtest import compare
from evallib.codegen import (build_code_prompt, strip_code_fence, make_ollama_code_ask,
                             load_subset_ids, pass_at_1)
from evallib.sandbox import subprocess_executor
from evallib.score import compute_gates, verdict, format_report

OLLAMA_URL = "http://localhost:11434"

def _code_pass_at_1(model, problems):
    code_ask = make_ollama_code_ask(model, OLLAMA_URL)
    completions = [strip_code_fence(code_ask(build_code_prompt(p))) for p in problems]
    return pass_at_1(problems, completions, subprocess_executor(timeout=10.0))["frac"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ft", required=True, help="nome do modelo fine-tunado no Ollama")
    ap.add_argument("--base", required=True, help="nome do modelo base no Ollama")
    ap.add_argument("--no-judge", action="store_true", help="pula T1+T2 (não usa a API do Claude)")
    a = ap.parse_args()

    probes = load_probes("data/probes.jsonl")

    # T0 — gerar dicas (ft e base) e medir formato/seletividade
    ft_ask = make_ollama_ask(a.ft, OLLAMA_URL)
    base_ask = make_ollama_ask(a.base, OLLAMA_URL)
    hints_ft = generate_hints(probes, ft_ask)
    hints_base = generate_hints(probes, base_ask)
    fmt_ft = score_format(probes, hints_ft)
    fmt_base = score_format(probes, hints_base)
    sel = score_selectivity(probes, hints_ft)

    # T1 + T2 — juiz (Claude). Só se houver chave e sem --no-judge.
    if a.no_judge:
        quality = {"overall_ft": 0.0, "overall_base": 0.0}
        ab = {"ft_wins": 0, "base_wins": 0, "ties": 0}
        print("[aviso] --no-judge: T1/T2 não rodaram; G1 será reprovado por padrão.", file=sys.stderr)
    else:
        from evallib.judge import make_claude_ask
        n_calls = len(probes) * 3  # T1 ft + T1 base + T2
        print(f"[info] vou fazer ~{n_calls} chamadas ao Claude (juiz). Ctrl-C para abortar.", file=sys.stderr)
        judge_ask = make_claude_ask()
        q_ft = score_quality(list(zip(probes, hints_ft)), judge_ask)
        q_base = score_quality(list(zip(probes, hints_base)), judge_ask)
        quality = {"overall_ft": q_ft["overall"], "overall_base": q_base["overall"]}
        ab = compare(probes, hints_ft, hints_base, judge_ask, seed=42)

    # T3 — regressão de código (HumanEval subset)
    from datasets import load_dataset
    ds = load_dataset("openai_humaneval", split="test")
    wanted = set(load_subset_ids("data/humaneval_subset.txt"))
    problems = [r for r in ds if r["task_id"] in wanted]
    code_ft = _code_pass_at_1(a.ft, problems)
    code_base = _code_pass_at_1(a.base, problems)

    results = {
        "format": {"ft": fmt_ft["frac"], "base": fmt_base["frac"]},
        "quality": quality,
        "ab": ab,
        "code": {"ft": code_ft, "base": code_base},
        "selectivity": {"correct": sel["correct"], "total": sel["total"]},
    }
    gates = compute_gates(results)
    report = format_report(results, gates)
    print(report)

    os.makedirs("reports", exist_ok=True)
    with open("reports/last.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "gates": gates, "verdict": verdict(gates)},
                  f, ensure_ascii=False, indent=2)

    sys.exit(0 if verdict(gates) == "PROMOVER" else 1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Confirm all unit tests still pass**

Run (de `eval/`): `python -m pytest -q`
Expected: PASS (todos os testes das Tasks 1-8).

- [ ] **Step 3: Manual E2E (baseline; precisa de Ollama + chave)**

Pré: Ollama com `professor-ft` e `qwen2.5-coder:14b` carregáveis; `export ANTHROPIC_API_KEY=...` (WSL; não commitar).
Run (de `eval/`):
```bash
python run_eval.py --ft professor-ft --base qwen2.5-coder:14b
```
Expected: imprime o relatório das 4 trilhas lado a lado + `>>> VEREDITO: ...`, grava `reports/last.json`. Este é o **baseline pedagógico** que o dry-run não mediu. Os limiares (95% / ε=5pp / wins>losses) são calibráveis em `evallib/score.py` à luz deste primeiro relatório.

Smoke barato sem gastar API (valida T0+T3 e a fiação): `python run_eval.py --ft professor-ft --base qwen2.5-coder:14b --no-judge`.

- [ ] **Step 4: Commit**

```bash
git add eval/run_eval.py eval/README.md
git commit -m "feat(eval): orchestrator run_eval (4 tracks + verdict, side-by-side report)"
```

---

## Notas de execução

- **Onde roda o quê:** Tasks 1-8 e os unit tests da 9 rodam em qualquer máquina (Python puro/mocks). O E2E real (Task 9, Step 3) precisa de Ollama (4080) + `ANTHROPIC_API_KEY`.
- **Segurança da chave:** `ANTHROPIC_API_KEY` só via env var; nunca em código/commit/doc. O `judge.make_claude_ask` falha alto se faltar.
- **Custo da API:** ~`len(probes)*3` chamadas ao Claude por corrida (T1 ft + T1 base + T2). Com ~40 probes ≈ 120 chamadas curtas em `claude-opus-4-8` — barato. `--no-judge` roda T0+T3 sem tocar a API.
- **Sem `temperature` no juiz:** Opus 4.8 rejeita `temperature`/`top_p`/`top_k` (400). Determinismo vem da rubrica explícita + parsing tolerante; o SDK já re-tenta 429/5xx sozinho.
- **Curadoria do probe set (Task 2, Step 3):** ~40 trechos curados, **disjuntos** do `seeds.jsonl` do treino — é o moat da régua e o que a torna um teste honesto entre versões.
- **A régua mede e recomenda; não promove.** O veredito PROMOVER habilita a troca de `professor.model`, mas a troca em si é ato deliberado da Fatia B3, fora deste plano.
- **Não commitar dados/relatórios baixados:** `reports/`, `hf_cache/` e o cache do dataset são gitignored.
```
