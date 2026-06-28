# Professor — Fine-tune Fatia B2: fábrica de dados (Design)

- **Data:** 2026-06-28
- **Status:** Design aprovado em conversa; aguardando revisão deste documento antes do plano.
- **Autor:** juaredbr + Claude
- **Depende de:** B1 (régua de avaliação) — reusa `eval/evallib/judge.py` (juiz Claude) para o QA.
  E da Fatia A (dry-run) — contrato de dados em `fine-tune/ftlib` (`is_valid_hint`, `build_dataset`).
- **Referências:** `docs/superpowers/specs/2026-06-27-finetune-fatiaB1-eval-design.md`,
  `docs/superpowers/specs/fine-tune-data-sources.md` (receita pedagógica: socrático + economia de palavras),
  `src/core/panorama.ts` (contrato do panorama), `fine-tune/ftlib/` (contrato do dataset).

## 1. Visão

Produzir, **em volume e com qualidade**, o dataset de treino do próximo `professor-ft`.
O dry-run (Fatia A) usou 61 sementes curadas à mão + 300 OCI = 361 exemplos — não escala.
A B1 provou (baseline ao vivo) que o `professor-ft` já é forte; o alvo agora não é mais o
base cru e sim **superar o próprio `professor-ft` (incumbente)**, medido pela régua B1.

A B2 entrega: o **pipeline de geração** (`fine-tune/datagen/`), o **dataset gerado**, e um
**relatório de QA**. NÃO treina nem troca produção — isso é a B3.

Terceira de três sub-fatias da Fatia B:
- **B1 — régua de avaliação** (feito; PR #2).
- **B2 — fábrica de dados em escala** (este spec).
- **B3 — treino em escala + troca em produção** (gated pela B1).

## 2. Objetivos e não-objetivos

Objetivos (os 4 confirmados na conversa):
- **Robustez de formato + escala** — 100% JSON válido por construção (fecha o gap de formato
  0.975 do dry-run) e muito mais volume diverso que os 361 do dry-run.
- **Cobertura de linguagens/cenários** — código real de várias linguagens e tipos de
  bug/code-smell, não só o nicho estreito do dry-run.
- **Qualidade socrática + seletividade** — dicas socráticas/concisas e boa calibração de
  quando CALAR (`skip`) vs ensinar (as trilhas que a régua T1/seletividade medem).
- **Incluir panorama (Fatia 2)** — segunda trilha de treino com o schema `{structure, next}`.

Não-objetivos (YAGNI):
- **Não** treina o modelo nem roda a régua final — isso é B3.
- **Não** troca `professor.model` em produção — B3.
- **Não** colhe dados de produção/RAG — ainda não há volume de uso real; a cobertura vem de
  código real multi-linguagem. (Futuro, quando houver telemetria de produção.)
- **Não** é um framework genérico de geração orientado a config; é focado neste dataset.

## 3. Decisões confirmadas (na conversa)

1. **Motor:** híbrido com **GLM 5.2 via OpenRouter** no volume (barato/escala); Claude só na
   amostra de QA (reusa juiz da B1). Colheita OCI para o código real.
2. **Fonte do código:** **código real, GLM só anota.** Puxa trechos reais (amostra OCI + amostra
   multi-linguagem para cobertura) e o GLM escreve só a dica/panorama. Mais realista, mais barato
   (menos tokens de saída), cobre linguagens variadas.
3. **Duas trilhas de saída:** **dica** `{comment, why, nudge, suggestion}|{skip}` e
   **panorama** `{structure, next}|{skip}`, cada uma com seu system prompt (reusados de `src/core`).
4. **Volume:** **calibrar e escalar até ~$4.** Lote-piloto (~50 ex) mede custo/qualidade reais →
   go/no-go → escala até gastar ~$4 (deixa folga sobre os $5). Provavelmente ~2-4k exemplos válidos.
5. **Estrutura:** pacote novo `fine-tune/datagen/` espelhando `ftlib`/`evallib` (funções puras
   testáveis + cliente plugável), schema-gated, com **teto rígido de orçamento**.
6. **Chave OpenRouter:** `OPENROUTER_API_KEY` no ambiente (igual `ANTHROPIC_API_KEY`, via `setx`,
   nunca commitada). Endpoint compatível-OpenAI.

## 4. Arquitetura

Pacote novo `fine-tune/datagen/`: **lógica pura testável (pytest, sem rede)** + **glue fina**
que fala com OpenRouter (GLM) e Claude (QA). Reusa de `fine-tune/ftlib` o contrato de dataset
(`is_valid_hint`, schema, `build_dataset`) e de `eval/evallib/judge.py` o juiz Claude.

```
fine-tune/datagen/
  __init__.py
  openrouter.py    # cliente GLM 5.2 (OpenAI-compat): chave via env, retries,
                   #   contabilidade de tokens+custo. make_glm_ask(model) -> ask(messages)
  codesource.py    # amostra código real (OCI + multi-linguagem) -> {code,lang} / {outline,lang}
  prompts.py       # system prompts de dica e panorama (espelham src/core), build_*_messages
  generate.py      # p/ cada snippet: monta prompt, chama GLM, parseia, valida schema
  quality.py       # dedup (hash de código normalizado), descarte de inválidos, balanceamento
  budget.py        # acumula custo, teto rígido (~$4), loop piloto->escala
  qa_sample.py     # amostra N gerados, juiz Claude (reusa eval), relatório de qualidade
  run_datagen.py   # orquestrador: piloto -> QA/custo -> escala -> escreve seeds/panorama
fine-tune/data/
  generated_hints.jsonl      # {code, lang, hint}    (novo, append do GLM)
  generated_panorama.jsonl   # {outline, lang, panorama}  (novo)
fine-tune/tests/             # pytest por módulo (funções puras)
```

`build_dataset.py` é **estendido** para consumir as duas trilhas geradas (dica + panorama)
além das sementes/OCI existentes, e emitir ChatML com o system prompt correto por trilha.

### Fluxo de dados

```
OCI / datasets multi-lang
        │ codesource.sample()
        ▼
  {code,lang} / {outline,lang}
        │ generate (prompts + make_glm_ask)        budget.charge() a cada chamada
        ▼                                           (para em ~$4)
  candidatos brutos (texto GLM)
        │ parse + is_valid_hint / parsePanorama     (descarta inválidos)
        ▼
  {code,lang,hint} / {outline,lang,panorama} válidos
        │ quality: dedup + balanceamento
        ▼
  generated_hints.jsonl / generated_panorama.jsonl
        │ qa_sample (juiz Claude) -> relatório
        ▼
  build_dataset.py (estendido) -> train.jsonl / heldout.jsonl
```

## 5. Componentes (interfaces)

- **`openrouter.make_glm_ask(model, *, url, on_usage)`** → `ask(messages) -> str`. Lê
  `OPENROUTER_API_KEY`; erro claro se faltar. Retry/backoff em 429/5xx. Reporta `usage`
  (tokens prompt/completion) via callback para o `budget`.
- **`codesource.sample_code(n, langs, seed)`** → lista `{code, lang}` (real, deduplicada,
  filtrada por tamanho). **`make_outline(code, lang)`** → esqueleto p/ panorama (assinaturas/
  estrutura, sem corpos), reproduzindo o que a extensão envia.
- **`prompts.build_hint_messages(code, lang)` / `build_panorama_messages(outline, lang)`** →
  mensagens ChatML com os system prompts canônicos (espelham `TUTOR_SYSTEM` / panorama BASE).
- **`generate.generate_one(item, ask, kind)`** → `{...item, hint|panorama}` ou `None` se
  inválido/parse falhou. **`generate_batch(items, ask, kind)`** → lista de válidos.
- **`quality.dedup(rows, key)` / `balance(rows, by, ratios)`** → puras, determinísticas.
- **`budget.Budget(ceiling_usd, price)`** → `.charge(usage)`, `.spent()`, `.over()` (sentinela
  para o orquestrador parar). Preço do GLM 5.2 configurável (calibrado no piloto).
- **`qa_sample.qa_report(rows, judge_ask, n, seed)`** → métricas (rubrica média, % skip
  apropriado) sobre amostra; reusa `eval/evallib/rubric.py`/`judge.py`.

## 6. Fluxo operacional (anti-surpresa de fatura)

1. **Piloto:** `run_datagen.py --pilot 50` → gera ~50, mede **custo real/ex**, **yield**
   (% válido pós-schema), **qualidade** (juiz na amostra). Imprime projeção: "para ~$4 ≈ N ex".
2. **Go/no-go:** usuário decide à luz do piloto (qualidade baixa → ajustar prompt; caro → reduzir alvo).
3. **Escala:** `run_datagen.py --budget 4.0` → gera até o teto, schema-gated, dedup contínuo.
4. **Build:** `build_dataset.py` (estendido) → `train.jsonl`/`heldout.jsonl` prontos p/ B3.
5. **Relatório:** `reports/datagen.json` (custo, contagens por trilha/linguagem, QA).

## 7. Controle de qualidade (camadas)

1. **Schema** — `is_valid_hint` / `parsePanorama`: só entram exemplos 100% válidos (fecha formato).
2. **Dedup** — hash de código normalizado evita repetição (diversidade real).
3. **Balanceamento** — por linguagem e razão skip/ensina (não enviesar p/ tagarelar).
4. **QA por juiz** — rubrica Claude na amostra antes de escalar (corta lixo cedo).
5. **Gate final** — a régua B1 no B3: o novo `professor-ft` só promove se PROMOVER vs incumbente.

## 8. Tratamento de erros

- Chave ausente → erro explícito antes de qualquer chamada (não gasta nada).
- 429/5xx do OpenRouter → retry com backoff; após N falhas, salva progresso parcial e para.
- Resposta do GLM não-parseável/ inválida → descarta o exemplo, conta no yield, segue.
- Teto de orçamento atingido → para limpo, escreve o que já gerou + relatório (idempotente/retomável).
- Geração é **append + retomável**: reexecutar continua de onde parou sem duplicar (dedup).

## 9. Testes (TDD, pytest, sem rede)

Por módulo, com `ask`/`judge` **fakes** (sem GLM/Claude reais):
- `openrouter`: monta corpo certo, lê env, parseia usage, retry (com fake transport).
- `codesource`: amostragem determinística, filtros de tamanho/linguagem, outline.
- `generate`: válido→mantém, inválido/parse-fail→None, ambas as trilhas.
- `quality`: dedup remove repetidos, balance respeita razões, determinismo.
- `budget`: charge acumula, over() dispara no teto, projeção correta.
- `qa_sample`: agrega métricas sobre amostra com juiz fake.
- `build_dataset` estendido: inclui as duas trilhas com o system correto; split determinístico.

## 10. Entregável e critério de pronto (B2)

- `fine-tune/datagen/` completo + testes verdes.
- `generated_hints.jsonl` + `generated_panorama.jsonl` gerados dentro do teto (~$4).
- `train.jsonl`/`heldout.jsonl` reconstruídos incluindo os dados gerados + panorama.
- `reports/datagen.json` com custo real, contagens e QA.
- **B2 termina aqui.** Treinar com este dataset, rodar a régua B1 e (se PROMOVER) trocar
  produção é a **B3**.

## 11. Riscos

- **Preço/qualidade do GLM 5.2 desconhecidos** → mitigado pelo piloto + teto rígido.
- **Licença do output** — confirmar termos do OpenRouter/GLM p/ uso do output em treino.
- **Outline para panorama** — reproduzir fielmente o esqueleto que a extensão envia (senão
  treina distribuição errada); espelhar a lógica de `src/core` o mais próximo possível.
- **Viés de skip** — GLM pode ensinar demais; o balanceamento e a métrica de seletividade cuidam.
