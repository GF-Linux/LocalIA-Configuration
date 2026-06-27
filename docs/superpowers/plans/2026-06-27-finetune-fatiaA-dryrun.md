# Fine-tune Fatia A — Dry-run de-risco Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provar o pipeline de fine-tune ponta a ponta com um dataset minúsculo — `dados → ChatML → QLoRA (Unsloth, Qwen2.5-Coder-14B) → GGUF → Ollama → smoke-eval` — confirmando que o modelo treinado carrega no Ollama e emite o JSON do Professor válido.

**Architecture:** Tudo em `fine-tune/`. As partes determinísticas (coleta/normalização, formatação ChatML, parse do smoke-eval) são Python puro testável com pytest, sem GPU. O treino/export/load são scripts executados na 4080 com checkpoint manual (não há como unit-testar GPU/Ollama barato). O critério final é o smoke-eval passar.

**Tech Stack:** Python 3.12, pytest, datasets (HuggingFace), Unsloth + transformers + trl (QLoRA 4-bit), llama.cpp/GGUF, Ollama.

## Global Constraints

- Dry-run = **só dicas** (não panorama). Critério de sucesso **binário**: o GGUF carrega no Ollama E emite JSON `{comment,why,nudge,suggestion}` parseável em ≥ metade dos trechos held-out. Qualidade pedagógica NÃO é avaliada aqui.
- Modelo base: **Qwen2.5-Coder-14B** (via Unsloth). Fallback documentado: 7B se o 14B não couber na 4080 — troca só o nome do modelo, sem reescrever o pipeline.
- Dataset dry-run: **~60 sementes de professor** (fabricadas via Claude Code) + **~300 amostras do OpenCodeInstruct** (CC BY 4.0). Split ~85/15 treino/held-out, determinístico (seed fixa).
- Formato físico: **ChatML**. Os exemplos de professor **espelham o prompt de runtime** (system = instrução tutor em PT pedindo o JSON; user = código(+fontes); assistant = JSON da dica). Reusar o texto-base do `groundedPromptBuilder` (Fatia 2) para o system não divergir.
- Schema da dica de treino: `{ "comment": str, "why": str, "nudge": str, "suggestion": str }` (e alguns exemplos `{"skip": true}` para ensinar seletividade). `source` é opcional e NÃO entra no dry-run.
- Atribuição CC BY 4.0 do OpenCodeInstruct registrada no `fine-tune/README.md`.
- Hardware: o pipeline **descarrega os modelos do Ollama antes de treinar** (libera VRAM). Spill para RAM é aceito (lento). O dry-run revela se cabe na VRAM.
- Treino/export/load rodam na 4080; data-prep/formatter/smoke-eval-parse rodam em qualquer máquina.

---

### Task 1: Scaffold do `fine-tune/` + harness de testes

**Files:**
- Create: `fine-tune/requirements.txt`
- Create: `fine-tune/requirements-gpu.txt`
- Create: `fine-tune/README.md`
- Create: `fine-tune/ftlib/__init__.py`
- Create: `fine-tune/ftlib/schema.py`
- Create: `fine-tune/tests/__init__.py`
- Test: `fine-tune/tests/test_schema.py`
- Create: `fine-tune/.gitignore`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `ftlib.schema.HINT_KEYS: tuple[str, ...]` = `("comment", "why", "nudge", "suggestion")`
  - `ftlib.schema.is_valid_hint(obj) -> bool` — True se `obj` é dict com as 4 chaves string não-vazias, OU `{"skip": true}`.

- [ ] **Step 1: Write the failing test**

`fine-tune/tests/test_schema.py`:
```python
from ftlib.schema import is_valid_hint, HINT_KEYS

def test_valid_full_hint():
    assert is_valid_hint({"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"})

def test_valid_skip():
    assert is_valid_hint({"skip": True})

def test_missing_field_invalid():
    assert not is_valid_hint({"comment": "c", "why": "w", "nudge": "n"})

def test_empty_field_invalid():
    assert not is_valid_hint({"comment": "", "why": "w", "nudge": "n", "suggestion": "s"})

def test_non_dict_invalid():
    assert not is_valid_hint("nope")
    assert not is_valid_hint(None)

def test_hint_keys_constant():
    assert HINT_KEYS == ("comment", "why", "nudge", "suggestion")
```

- [ ] **Step 2: Run test to verify it fails**

Run (de `fine-tune/`): `python -m pytest tests/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ftlib.schema'`.

- [ ] **Step 3: Create project files**

`fine-tune/requirements.txt` (CPU — data-prep/formatter/eval-parse):
```
datasets==2.20.0
pytest==8.2.0
```

`fine-tune/requirements-gpu.txt` (4080 — treino; instalado à parte):
```
# Instalar conforme a model card do Unsloth para a sua CUDA. Referência:
# pip install "unsloth[cu124-torch250] @ git+https://github.com/unslothai/unsloth.git"
unsloth
trl
transformers
```

`fine-tune/.gitignore`:
```
__pycache__/
*.pyc
.venv/
data/*.jsonl
outputs/
*.gguf
hf_cache/
```

`fine-tune/README.md`:
```markdown
# Professor — Fine-tune (Fatia A: dry-run)

Pipeline de de-risco: dados → ChatML → QLoRA (Qwen2.5-Coder-14B, Unsloth) → GGUF → Ollama → smoke-eval.

## Atribuição
Usa uma amostra do dataset **nvidia/OpenCodeInstruct** (Hugging Face), licença **CC BY 4.0**.
Atribuição: NVIDIA, OpenCodeInstruct, https://huggingface.co/datasets/nvidia/OpenCodeInstruct

## Ambiente
- CPU (data-prep/formatter/eval): `pip install -r requirements.txt`
- GPU (treino, na 4080): ver `requirements-gpu.txt` + model card do Unsloth.

## Pipeline (ordem)
1. `python -m ftlib.collect_seeds`        # valida as sementes de professor
2. `python -m ftlib.collect_oci --n 300`  # baixa amostra do OpenCodeInstruct
3. `python -m ftlib.build_dataset`        # → data/train.jsonl + data/heldout.jsonl (ChatML)
4. `python train.py`                      # QLoRA na 4080 → outputs/adapter
5. `python export_gguf.py`                # → outputs/professor-ft.gguf
6. `ollama create professor-ft -f Modelfile`
7. `python -m ftlib.smoke_eval`           # roda held-out pelo Ollama, conta JSON válido
```

`fine-tune/ftlib/__init__.py`: (vazio)
`fine-tune/tests/__init__.py`: (vazio)

`fine-tune/ftlib/schema.py`:
```python
HINT_KEYS = ("comment", "why", "nudge", "suggestion")

def is_valid_hint(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("skip") is True:
        return True
    return all(isinstance(obj.get(k), str) and obj.get(k).strip() for k in HINT_KEYS)
```

- [ ] **Step 4: Install deps and run test to verify it passes**

Run (de `fine-tune/`): `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\python -m pytest tests/test_schema.py -v`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add fine-tune/
git commit -m "feat(ft): scaffold fine-tune dir + hint schema validator"
```

---

### Task 2: Sementes de professor (dataset curado) + loader validado

**Files:**
- Create: `fine-tune/data/seeds.jsonl`
- Create: `fine-tune/ftlib/collect_seeds.py`
- Test: `fine-tune/tests/test_collect_seeds.py`

**Interfaces:**
- Consumes: `ftlib.schema.is_valid_hint` (Task 1).
- Produces:
  - `ftlib.collect_seeds.load_seeds(path: str) -> list[dict]` — lê JSONL; cada linha = `{"code": str, "lang": str, "hint": dict}`; valida que `hint` passa `is_valid_hint` e que `code`/`lang` são strings não-vazias; lança `ValueError` em linha inválida.
  - O arquivo `data/seeds.jsonl` com **~60 exemplos** curados (fabricados pelo implementador via Claude — ver Step 3).

- [ ] **Step 1: Write the failing test**

`fine-tune/tests/test_collect_seeds.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collect_seeds.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Create the loader and the curated seeds file**

`fine-tune/ftlib/collect_seeds.py`:
```python
import json
from ftlib.schema import is_valid_hint

def load_seeds(path: str) -> list[dict]:
    seeds = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not (isinstance(row.get("code"), str) and row["code"].strip()):
                raise ValueError(f"linha {i}: 'code' ausente/vazio")
            if not (isinstance(row.get("lang"), str) and row["lang"].strip()):
                raise ValueError(f"linha {i}: 'lang' ausente/vazio")
            if not is_valid_hint(row.get("hint")):
                raise ValueError(f"linha {i}: 'hint' inválido")
            seeds.append(row)
    return seeds
```

`fine-tune/data/seeds.jsonl` — **fabricar ~60 exemplos curados** (uma linha JSON por exemplo) no formato:
```json
{"code": "f = open('dados.txt')\nconteudo = f.read()", "lang": "python", "hint": {"comment": "Você abre o arquivo mas não o fecha.", "why": "Sem fechar, o handle pode vazar; 'with' fecha automaticamente mesmo com exceção.", "nudge": "Envolva a leitura num bloco 'with open(...) as f:'.", "suggestion": "with open('dados.txt') as f:\n    conteudo = f.read()"}}
```
Diretrizes para os ~60:
- Variar linguagem (maioria Python; alguns JS/TS) e tema (recursos não fechados, list comprehension, mutável como default, igualdade vs identidade, etc.).
- Incluir **~8 exemplos `{"skip": true}`** sobre código trivial/correto (ensina a calar).
- Texto em PT-BR, conciso, estilo professor (porquê + empurrão, não a solução mastigada inteira).
- Curar à mão a qualidade — é o moat. (O implementador autora estes via Claude.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_collect_seeds.py -v`
Expected: PASS (4 testes; o último confirma ≥50 sementes reais).

- [ ] **Step 5: Commit**

```bash
git add fine-tune/ftlib/collect_seeds.py fine-tune/tests/test_collect_seeds.py fine-tune/data/seeds.jsonl
git commit -m "feat(ft): curated professor seed dataset + validated loader"
```

---

### Task 3: Amostra do OpenCodeInstruct

**Files:**
- Create: `fine-tune/ftlib/collect_oci.py`
- Test: `fine-tune/tests/test_collect_oci.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `ftlib.collect_oci.normalize_oci_row(row: dict) -> dict | None` — mapeia uma linha do OpenCodeInstruct (`{"input": str, "output": str, ...}`) para `{"instruction": str, "response": str}`; retorna `None` se `input`/`output` faltarem ou forem vazios.
  - `ftlib.collect_oci.main(n: int, out_path: str)` — baixa o split `train` do dataset via `datasets.load_dataset`, normaliza as `n` primeiras linhas válidas, grava JSONL em `out_path`. (Executável: `python -m ftlib.collect_oci --n 300`.)

- [ ] **Step 1: Write the failing test (pure normalize)**

`fine-tune/tests/test_collect_oci.py`:
```python
from ftlib.collect_oci import normalize_oci_row

def test_normalizes_valid_row():
    r = normalize_oci_row({"input": "Write a function", "output": "def f(): pass", "domain": "generic"})
    assert r == {"instruction": "Write a function", "response": "def f(): pass"}

def test_drops_empty():
    assert normalize_oci_row({"input": "", "output": "x"}) is None
    assert normalize_oci_row({"input": "x", "output": ""}) is None
    assert normalize_oci_row({"output": "x"}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_collect_oci.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the module**

`fine-tune/ftlib/collect_oci.py`:
```python
import argparse, json

def normalize_oci_row(row: dict) -> dict | None:
    inp = row.get("input")
    out = row.get("output")
    if not (isinstance(inp, str) and inp.strip() and isinstance(out, str) and out.strip()):
        return None
    return {"instruction": inp, "response": out}

def main(n: int, out_path: str) -> int:
    from datasets import load_dataset
    ds = load_dataset("nvidia/OpenCodeInstruct", split="train", streaming=True)
    written = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for row in ds:
            norm = normalize_oci_row(row)
            if norm is None:
                continue
            f.write(json.dumps(norm, ensure_ascii=False) + "\n")
            written += 1
            if written >= n:
                break
    return written

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default="data/oci.jsonl")
    a = ap.parse_args()
    print("escritas:", main(a.n, a.out))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_collect_oci.py -v`
Expected: PASS (2 testes). (O `main` que baixa de rede NÃO é unit-testado — é exercido na execução real do pipeline, Step 5.)

- [ ] **Step 5: Smoke-run the download (manual, needs internet)**

Run: `python -m ftlib.collect_oci --n 300 --out data/oci.jsonl`
Expected: imprime `escritas: 300`; cria `data/oci.jsonl` com 300 linhas `{instruction,response}`. (`data/*.jsonl` é gitignored — não commitar o dado baixado.)

- [ ] **Step 6: Commit**

```bash
git add fine-tune/ftlib/collect_oci.py fine-tune/tests/test_collect_oci.py
git commit -m "feat(ft): OpenCodeInstruct sample collector (normalize + streaming download)"
```

---

### Task 4: Formatter ChatML + montagem do dataset (split determinístico)

**Files:**
- Create: `fine-tune/ftlib/format_chatml.py`
- Create: `fine-tune/ftlib/build_dataset.py`
- Test: `fine-tune/tests/test_format_chatml.py`

**Interfaces:**
- Consumes: `load_seeds` (Task 2), `normalize_oci_row` output shape (Task 3).
- Produces:
  - `ftlib.format_chatml.TUTOR_SYSTEM: str` — o system de tutor (espelha o `groundedPromptBuilder` da Fatia 2; PT; pede o JSON).
  - `ftlib.format_chatml.seed_to_chatml(seed: dict) -> dict` — `{"messages": [{role,content}x3]}`: system=TUTOR_SYSTEM, user=código, assistant=`json.dumps(hint)`.
  - `ftlib.format_chatml.oci_to_chatml(row: dict) -> dict` — `{"messages": [...]}`: system=instrução genérica de código, user=instruction, assistant=response.
  - `ftlib.build_dataset.split_deterministic(items: list, frac_heldout: float, seed: int) -> tuple[list, list]`.
  - `ftlib.build_dataset.main()` — lê `data/seeds.jsonl` + `data/oci.jsonl`, formata, embaralha com seed fixa, faz split 85/15, grava `data/train.jsonl` e `data/heldout.jsonl`.

- [ ] **Step 1: Write the failing test**

`fine-tune/tests/test_format_chatml.py`:
```python
import json
from ftlib.format_chatml import seed_to_chatml, oci_to_chatml, TUTOR_SYSTEM
from ftlib.build_dataset import split_deterministic

def test_seed_to_chatml_shape():
    seed = {"code": "open('f')", "lang": "python",
            "hint": {"comment": "c", "why": "w", "nudge": "n", "suggestion": "s"}}
    msg = seed_to_chatml(seed)["messages"]
    assert [m["role"] for m in msg] == ["system", "user", "assistant"]
    assert msg[0]["content"] == TUTOR_SYSTEM
    assert "open('f')" in msg[1]["content"]
    assert json.loads(msg[2]["content"]) == seed["hint"]  # assistant é JSON parseável

def test_tutor_system_mentions_json_and_pt():
    s = TUTOR_SYSTEM.lower()
    assert "json" in s and "portugu" in s

def test_oci_to_chatml_shape():
    msg = oci_to_chatml({"instruction": "Write f", "response": "def f(): pass"})["messages"]
    assert [m["role"] for m in msg] == ["system", "user", "assistant"]
    assert msg[1]["content"] == "Write f"
    assert msg[2]["content"] == "def f(): pass"

def test_split_deterministic_is_stable_and_disjoint():
    items = list(range(100))
    a1, b1 = split_deterministic(items, 0.15, seed=42)
    a2, b2 = split_deterministic(items, 0.15, seed=42)
    assert (a1, b1) == (a2, b2)            # determinístico
    assert len(b1) == 15 and len(a1) == 85 # split correto
    assert set(a1).isdisjoint(set(b1))     # sem vazamento
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_format_chatml.py -v`
Expected: FAIL — módulos não existem.

- [ ] **Step 3: Write the formatter**

`fine-tune/ftlib/format_chatml.py`:
```python
import json

TUTOR_SYSTEM = (
    "Você é um professor de programação que ensina na prática, em português do Brasil. "
    "Olhe o trecho de código do aluno e, se houver UM ponto de aprendizado relevante, ensine "
    "o PORQUÊ e o idioma correto, sem reescrever todo o código. Se não houver nada que valha "
    "a pena ensinar, responda {\"skip\": true}. Responda SOMENTE em JSON válido no formato "
    "{\"comment\":\"...\",\"why\":\"...\",\"nudge\":\"...\",\"suggestion\":\"...\"}."
)

CODE_SYSTEM = "You are a helpful coding assistant. Answer the task with correct code."

def seed_to_chatml(seed: dict) -> dict:
    return {"messages": [
        {"role": "system", "content": TUTOR_SYSTEM},
        {"role": "user", "content": f"Linguagem: {seed['lang']}\nCódigo:\n{seed['code']}"},
        {"role": "assistant", "content": json.dumps(seed["hint"], ensure_ascii=False)},
    ]}

def oci_to_chatml(row: dict) -> dict:
    return {"messages": [
        {"role": "system", "content": CODE_SYSTEM},
        {"role": "user", "content": row["instruction"]},
        {"role": "assistant", "content": row["response"]},
    ]}
```

- [ ] **Step 4: Write the dataset builder**

`fine-tune/ftlib/build_dataset.py`:
```python
import json, random
from ftlib.collect_seeds import load_seeds
from ftlib.format_chatml import seed_to_chatml, oci_to_chatml

def split_deterministic(items, frac_heldout, seed):
    rng = random.Random(seed)
    shuffled = items[:]
    rng.shuffle(shuffled)
    n_held = round(len(shuffled) * frac_heldout)
    heldout = shuffled[:n_held]
    train = shuffled[n_held:]
    return train, heldout

def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def main():
    seeds = [seed_to_chatml(s) for s in load_seeds("data/seeds.jsonl")]
    oci = [oci_to_chatml(r) for r in _read_jsonl("data/oci.jsonl")]
    items = seeds + oci
    train, heldout = split_deterministic(items, 0.15, seed=42)
    _write_jsonl("data/train.jsonl", train)
    _write_jsonl("data/heldout.jsonl", heldout)
    print(f"train={len(train)} heldout={len(heldout)} (seeds={len(seeds)} oci={len(oci)})")

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_format_chatml.py -v`
Expected: PASS (4 testes).

- [ ] **Step 6: Build the real dataset (manual; needs seeds + oci.jsonl present)**

Run: `python -m ftlib.build_dataset`
Expected: imprime `train=... heldout=...`; cria `data/train.jsonl` e `data/heldout.jsonl`. (gitignored.)

- [ ] **Step 7: Commit**

```bash
git add fine-tune/ftlib/format_chatml.py fine-tune/ftlib/build_dataset.py fine-tune/tests/test_format_chatml.py
git commit -m "feat(ft): ChatML formatter + deterministic dataset split"
```

---

### Task 5: Script de treino QLoRA (Unsloth) — executado na 4080

**Files:**
- Create: `fine-tune/train.py`

**Interfaces:**
- Consumes: `data/train.jsonl` (Task 4).
- Produces: `outputs/adapter/` (adapter LoRA salvo).

**Nota:** este script roda na 4080 com `requirements-gpu.txt`. Não há unit test (GPU). A validação é a execução manual completar e salvar o adapter; o critério final é o smoke-eval (Task 8).

- [ ] **Step 1: Write the training script**

`fine-tune/train.py`:
```python
"""QLoRA dry-run: Qwen2.5-Coder-14B com Unsloth. Roda na 4080.
Antes de rodar: descarregue modelos do Ollama (libera VRAM):  ollama stop qwen3:14b
Se o 14B não couber, troque BASE_MODEL pelo 7B (ver README) — resto inalterado."""
import json
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig
from datasets import load_dataset

BASE_MODEL = "unsloth/Qwen2.5-Coder-14B-Instruct"  # fallback: ...-7B-Instruct
MAX_SEQ = 2048

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL, max_seq_length=MAX_SEQ, load_in_4bit=True,
)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=16, lora_dropout=0,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth",
)

ds = load_dataset("json", data_files="data/train.jsonl", split="train")
def to_text(ex):
    return {"text": tokenizer.apply_chat_template(ex["messages"], tokenize=False)}
ds = ds.map(to_text)

trainer = SFTTrainer(
    model=model, tokenizer=tokenizer, train_dataset=ds,
    args=SFTConfig(
        dataset_text_field="text", max_seq_length=MAX_SEQ,
        per_device_train_batch_size=1, gradient_accumulation_steps=8,
        num_train_epochs=1, learning_rate=2e-4, logging_steps=5,
        output_dir="outputs/ckpt", optim="adamw_8bit", seed=42,
    ),
)
trainer.train()
model.save_pretrained("outputs/adapter")
tokenizer.save_pretrained("outputs/adapter")
print("adapter salvo em outputs/adapter")
```

- [ ] **Step 2: Manual run on the 4080 (checkpoint with human)**

Pré: ambiente GPU instalado; `data/train.jsonl` presente; Ollama com a VRAM liberada (`ollama stop qwen3:14b`).
Run: `python train.py`
Expected: treino de 1 época completa; salva `outputs/adapter`. **Se estourar VRAM:** trocar `BASE_MODEL` para `unsloth/Qwen2.5-Coder-7B-Instruct` e rodar de novo (documenta o fallback no relatório). Esse passo REVELA se o 14B cabe.

- [ ] **Step 3: Commit**

```bash
git add fine-tune/train.py
git commit -m "feat(ft): QLoRA training script (Unsloth, Qwen2.5-Coder-14B)"
```

---

### Task 6: Export para GGUF — executado na 4080

**Files:**
- Create: `fine-tune/export_gguf.py`
- Create: `fine-tune/Modelfile`

**Interfaces:**
- Consumes: `outputs/adapter/` (Task 5).
- Produces: `outputs/professor-ft.gguf` (modelo merge+quantizado) e o `Modelfile` do Ollama.

- [ ] **Step 1: Write the export script**

`fine-tune/export_gguf.py`:
```python
"""Merge do adapter + export GGUF (q4_k_m). Roda na 4080, após train.py.
Usa o utilitário do Unsloth para salvar direto em GGUF."""
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="outputs/adapter", max_seq_length=2048, load_in_4bit=True,
)
model.save_pretrained_gguf("outputs", tokenizer, quantization_method="q4_k_m")
print("GGUF gerado em outputs/ (q4_k_m)")
```

- [ ] **Step 2: Create the Modelfile**

`fine-tune/Modelfile`:
```
FROM ./outputs/professor-ft.gguf
PARAMETER temperature 0.3
PARAMETER num_ctx 2048
```
(Ajustar o nome do `.gguf` em `FROM` para o arquivo realmente gerado pelo Unsloth.)

- [ ] **Step 3: Manual run on the 4080 (checkpoint with human)**

Run: `python export_gguf.py`
Expected: gera um `.gguf` em `outputs/`. Anote o nome exato do arquivo gerado e ajuste o `Modelfile` se necessário.

- [ ] **Step 4: Commit**

```bash
git add fine-tune/export_gguf.py fine-tune/Modelfile
git commit -m "feat(ft): GGUF export + Ollama Modelfile"
```

---

### Task 7: Carregar no Ollama — executado na 4080

**Files:** (nenhum novo; passo operacional documentado no README)

**Interfaces:**
- Consumes: `outputs/professor-ft.gguf` + `Modelfile` (Task 6).
- Produces: o modelo `professor-ft` registrado no Ollama local.

- [ ] **Step 1: Create the model in Ollama (manual)**

Run (de `fine-tune/`): `ollama create professor-ft -f Modelfile`
Expected: `ollama list` mostra `professor-ft`. Sanidade:
```
ollama run professor-ft "Linguagem: python\nCódigo:\nf = open('x')\nconteudo = f.read()"
```
Expected: devolve algo em JSON com `comment/why/nudge/suggestion` (qualidade não importa aqui — só que carrega e responde no formato).

- [ ] **Step 2: Commit (doc only, if README updated)**

```bash
git add fine-tune/README.md
git commit -m "docs(ft): ollama create step for professor-ft"
```

---

### Task 8: Smoke-eval — valida o critério binário do dry-run

**Files:**
- Create: `fine-tune/ftlib/smoke_eval.py`
- Test: `fine-tune/tests/test_smoke_eval.py`

**Interfaces:**
- Consumes: `data/heldout.jsonl` (Task 4), o modelo `professor-ft` no Ollama (Task 7), `ftlib.schema.is_valid_hint` (Task 1).
- Produces:
  - `ftlib.smoke_eval.extract_json(raw: str) -> dict | None` — extrai o 1º objeto JSON de um texto (mesma tolerância do `parseHint` da extensão: acha `{`…`}`, tenta `json.loads`, `None` se falhar).
  - `ftlib.smoke_eval.score(records: list[tuple[str, str]], asker) -> dict` — para cada held-out (só os do professor, ie. system == TUTOR_SYSTEM), pergunta ao modelo via `asker(messages)->str`, conta quantos produzem `is_valid_hint`. Retorna `{"total": int, "valid": int, "frac": float}`. (`asker` injetado → testável com mock.)
  - `main()` — roda `score` com um `asker` real (HTTP ao Ollama local `/api/chat`), imprime o resultado, e sai com código 0 se `frac >= 0.5`, senão 1.

- [ ] **Step 1: Write the failing test (pure logic, mocked asker)**

`fine-tune/tests/test_smoke_eval.py`:
```python
from ftlib.smoke_eval import extract_json, score
from ftlib.format_chatml import TUTOR_SYSTEM

def test_extract_json_tolerates_junk():
    assert extract_json('lixo {"comment":"c"} fim') == {"comment": "c"}
    assert extract_json("sem json") is None

def _rec(code):
    return {"messages": [
        {"role": "system", "content": TUTOR_SYSTEM},
        {"role": "user", "content": code},
        {"role": "assistant", "content": "{}"},
    ]}

def test_score_counts_valid_json_hints():
    held = [_rec("a"), _rec("b"), _rec("c")]
    # asker devolve: 2 válidos, 1 inválido
    replies = iter([
        '{"comment":"c","why":"w","nudge":"n","suggestion":"s"}',
        'isso não é json',
        '{"skip": true}',
    ])
    def asker(messages):  # ignora o conteúdo, devolve a próxima resposta
        return next(replies)
    out = score(held, asker)
    assert out == {"total": 3, "valid": 2, "frac": 2/3}

def test_score_ignores_non_tutor_records():
    code_rec = {"messages": [
        {"role": "system", "content": "You are a helpful coding assistant. Answer the task with correct code."},
        {"role": "user", "content": "Write f"},
        {"role": "assistant", "content": "def f(): pass"},
    ]}
    def asker(messages):
        return "qualquer coisa"
    out = score([code_rec], asker)
    assert out == {"total": 0, "valid": 0, "frac": 0.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke_eval.py -v`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the module**

`fine-tune/ftlib/smoke_eval.py`:
```python
import json, urllib.request
from ftlib.schema import is_valid_hint
from ftlib.format_chatml import TUTOR_SYSTEM

def extract_json(raw: str):
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return None

def score(records: list[dict], asker) -> dict:
    tutor = [r for r in records if r["messages"][0]["content"] == TUTOR_SYSTEM]
    valid = 0
    for r in tutor:
        # manda só system+user (sem o assistant de referência)
        prompt = [r["messages"][0], r["messages"][1]]
        reply = asker(prompt)
        if is_valid_hint(extract_json(reply or "")):
            valid += 1
    total = len(tutor)
    return {"total": total, "valid": valid, "frac": (valid / total) if total else 0.0}

def _ollama_asker(model: str, url: str):
    def ask(messages):
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["message"]["content"]
    return ask

def main():
    import sys
    with open("data/heldout.jsonl", encoding="utf-8") as f:
        held = [json.loads(l) for l in f if l.strip()]
    asker = _ollama_asker("professor-ft", "http://localhost:11434")
    out = score(held, asker)
    print(f"smoke-eval: {out['valid']}/{out['total']} JSON válido (frac={out['frac']:.2f})")
    sys.exit(0 if out["frac"] >= 0.5 else 1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_smoke_eval.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Run the real smoke-eval against professor-ft (manual; on the 4080)**

Pré: `professor-ft` criado no Ollama (Task 7); `data/heldout.jsonl` presente.
Run: `python -m ftlib.smoke_eval`
Expected: imprime `smoke-eval: X/Y JSON válido (frac=...)`. **Critério de pronto do dry-run: `frac >= 0.5`** (exit 0). Se < 0.5, o pipeline funciona mas o modelo não aprendeu o formato — anota e vira input pra Fatia B (mais dados/épocas).

- [ ] **Step 6: Commit**

```bash
git add fine-tune/ftlib/smoke_eval.py fine-tune/tests/test_smoke_eval.py
git commit -m "feat(ft): smoke-eval (held-out JSON-validity, the dry-run pass/fail gate)"
```

---

## Notas de execução

- **Onde roda o quê:** Tasks 1-4 e os unit tests da 8 rodam em qualquer máquina (Python puro). Tasks 5-7 e o smoke-eval real (8, Step 5) rodam **na 4080** com o ambiente GPU.
- **Fabricar as sementes (Task 2, Step 3):** o implementador autora ~60 exemplos curados via Claude — é o conteúdo de maior valor do dry-run. Qualidade > quantidade.
- **Liberar VRAM antes de treinar:** `ollama stop qwen3:14b` (e quaisquer modelos carregados) — o treino do 14B precisa de quase toda a VRAM.
- **Fallback 7B:** se o 14B estourar a VRAM na Task 5, trocar `BASE_MODEL` para o 7B (uma linha) e seguir igual. O dry-run existe para revelar isso.
- **Critério de pronto (binário):** smoke-eval com `frac >= 0.5` em held-out de professor = pipeline validado. Qualidade pedagógica e a troca do `professor.model` em produção são da Fatia B.
- **Não commitar dados baixados/treinados:** `data/*.jsonl` (exceto `seeds.jsonl`), `outputs/`, `*.gguf` são gitignored.
