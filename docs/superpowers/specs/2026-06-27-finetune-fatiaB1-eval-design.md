# Professor — Fine-tune Fatia B1: régua de avaliação (Design)

- **Data:** 2026-06-27
- **Status:** Design aprovado em conversa; aguardando revisão deste documento antes do plano.
- **Autor:** juaredbr + Claude
- **Depende de:** Fine-tune Fatia A (dry-run) — pipeline validado, `professor-ft` no Ollama.
- **Referências:** `docs/superpowers/specs/2026-06-27-finetune-fatiaA-dryrun-design.md` (§11 — próxima fatia),
  `docs/superpowers/specs/fine-tune-data-sources.md` (receita pedagógica: socrático + economia de palavras).

## 1. Visão

Construir a **régua** que mede se um modelo do Professor ficou de fato melhor — antes de
investir no dataset cheio (B2) e antes de qualquer troca em produção (B3). O dry-run (Fatia A)
provou **formato** (6/6 JSON válido) mas **não** mediu qualidade pedagógica nem regressão de
código. A B1 fecha essa lacuna: dá um baseline imediato (`professor-ft` vs. Qwen base) e define,
de forma operacional, o que significa "melhor".

Esta é a primeira de três sub-fatias da Fatia B (decompostas nesta conversa):
- **B1 — régua de avaliação** (este spec).
- **B2 — fábrica de dados em escala** (sementes via Claude/GLM 5.2/colheita do RAG + panorama + OCI).
- **B3 — treino em escala + troca em produção** (gated pela B1).

## 2. Objetivos e não-objetivos

Objetivos:
- Medir um modelo do Professor em **4 trilhas**: validade de formato, qualidade pedagógica
  (LLM-judge), A/B cego vs. base, regressão de código.
- Produzir um **veredito de promoção** (PROMOVER / NÃO PROMOVER) com portões claros.
- Régua **fixa e reprodutível** entre versões, para comparação honesta.
- Rodável já contra o `professor-ft` atual e o `qwen2.5-coder:14b` base → primeiro baseline.

Não-objetivos (YAGNI):
- **Não** executa a troca de `professor.model` em produção — isso é B3, e só se a B1 disser PROMOVER.
- **Não** gera o dataset de treino — isso é B2.
- **Não** é um harness genérico orientado a config (YAML de trilhas/thresholds); é focado em um
  modelo/decisão. Limiares ficam como constantes configuráveis no código.
- **Não** mede panorama (`structure/next`) ainda — a B1 foca o caminho principal (dicas), como a Fatia A.

## 3. Decisões confirmadas (na conversa)

1. **Trilhas:** as 4 — formato/JSON, qualidade pedagógica (LLM-judge), A/B cego vs. base,
   regressão de código.
2. **Conjunto de teste:** **probe set curado independente** (~30-50 trechos com momentos de
   ensino conhecidos), **separado** dos dados de treino (evita vazamento; teste estável).
3. **Modelo-juiz:** **Claude via API** (juiz forte e isento; desacopla do GLM 5.2, que será
   gerador de dados na B2).
4. **Regressão de código:** **HumanEval oficial** (pacote `human-eval`), **subset fixo** (~35
   dos 164), geração via Ollama **sem o system de tutor**, execução **sandboxed** no WSL com timeout.
5. **Estrutura:** pacote `eval/` separado, espelhando o `fine-tune/` (módulos puros + glue),
   reusando o contrato de runtime de `fine-tune/ftlib`.

## 4. Arquitetura

Pacote novo `eval/`: **lógica pura testável (pytest, sem GPU/rede)** + **glue fina** que fala
com Ollama (local) e Claude (API). Reusa de `fine-tune/ftlib` o contrato de runtime
(`is_valid_hint`, `TUTOR_SYSTEM`, `extract_json`) para medir exatamente o que o Professor faz.

```
eval/
  evallib/
    probes.py        # PURO: carrega/valida o probe set (~40 trechos curados)
    runners.py       # glue: gera dicas — askProfessor(model, probe) via Ollama
    judge.py         # glue: cliente Claude (API) + parse do veredito (lógica de parse pura)
    rubric.py        # PURO: texto da rubrica + parse/validação da nota (5 critérios)
    abtest.py        # PURO: monta par cego (randomiza ordem), de-anonimiza o vencedor
    codegen.py       # glue: gera soluções HumanEval via Ollama (sem system tutor)
    sandbox.py       # glue: executa solução HumanEval com timeout no WSL (lógica pass/fail pura)
    score.py         # PURO: agrega as 4 trilhas → relatório + gate de decisão
  data/
    probes.jsonl          # probe set curado (versionado — é o moat da régua)
    humaneval_subset.txt  # ids fixos do subset (~35 problemas)
  run_eval.py        # orquestrador: roda as trilhas para 1+ modelos, grava relatório
  tests/             # pytest das partes puras
  README.md
```

**Princípio de isolamento:** cada trilha é uma unidade com entrada/saída claras. As partes
*puras* (probes, rubric, abtest, score, e a lógica de parse/contagem das de glue) são testadas
sem tocar rede; as de *glue* (chamada Ollama/Claude, execução do sandbox) têm a parte testável
extraída para função pura + mock — mesmo padrão do `smoke_eval.score(records, asker)` da Fatia A.

**Quem fala com quê:** `runners`/`codegen`/`sandbox` → Ollama local (`professor-ft` e Qwen base).
`judge` → Claude via API. Todo o resto é offline/puro.

## 5. Componentes

1. **probes** (puro): carrega `data/probes.jsonl`. Cada probe = `{id, code, lang, teaching_point,
   should_skip: bool}`. Valida campos; `should_skip=true` marca os casos "não há o que ensinar".
2. **runners** (glue): para um modelo e um probe, monta o prompt de runtime (system=TUTOR_SYSTEM,
   user=código) e chama o Ollama → texto cru da dica.
3. **judge** (glue + parse puro): cliente Claude. Recebe (probe + dica + rubrica), devolve o
   veredito JSON. A função de parse/validação do veredito é pura e testável com mock.
4. **rubric** (puro): o texto da rubrica (5 critérios) e o parse/validação da nota.
5. **abtest** (puro): monta o par cego com ordem randomizada (seed fixa) e rótulos A/B anônimos;
   de-anonimiza o vencedor escolhido pelo juiz de volta ao modelo certo; conta win/lose/tie.
6. **codegen** (glue): gera soluções para o subset HumanEval via Ollama, **sem** o system de
   tutor (modo code-completer, não-JSON).
7. **sandbox** (glue + lógica pura): executa cada solução HumanEval isolada, com timeout, no WSL;
   computa pass@1. A lógica pass/fail é pura e testável com resultados simulados.
8. **score** (puro): agrega as 4 trilhas, computa os 4 portões e o veredito final.
9. **run_eval** (orquestrador): recebe 1+ modelos, roda as trilhas (com flags para rodar
   subconjuntos), grava relatório JSON + resumo legível. Loga o nº de chamadas ao Claude antes
   de disparar a trilha do juiz.

## 6. Fluxo de dados (as 4 trilhas)

A régua é **fixa entre modelos**: o mesmo probe set, a mesma rubrica e o mesmo subset HumanEval
rodam em todos os modelos comparados.

**Trilha 0 — Formato (gate de sanidade, barato).** Para cada probe → dica via Ollama →
`is_valid_hint(extract_json(...))`. Dois usos do mesmo número, distintos: (a) **cutoff
operacional** — se um modelo fica abaixo de um piso baixo (ex.: 50%) aqui, as trilhas caras
(juiz/API) nem rodam para ele, para não gastar à toa num modelo claramente quebrado; (b) o
**portão de promoção G0** (§8) é mais exigente (≥ 95%). O cutoff evita desperdício; o portão decide promoção.

**Trilha 1 — Qualidade pedagógica (LLM-judge).** Para cada probe (não-skip) → dica do modelo →
Claude pontua 1-5 em 5 critérios + justificativa → média por critério e global.

**Trilha 2 — A/B cego vs. base.** Para cada probe, dica do `professor-ft` **e** do base → par
cego com ordem randomizada → Claude escolhe a melhor às cegas → de-anonimiza → win/lose/tie.

**Trilha 3 — Regressão de código.** `codegen` gera soluções do subset HumanEval via Ollama (sem
system de tutor) → `sandbox` executa com timeout → pass@1, no fine-tunado e no base.

**Seletividade (sub-medida da Trilha 0):** nos probes `should_skip=true`, conta se o modelo
corretamente calou (`{"skip": true}`). Registrada à parte da rubrica de 5 critérios.

**Saída:** `score` junta tudo num relatório (JSON + resumo) por modelo, lado a lado.

## 7. Rubrica pedagógica (5 critérios, nota 1-5)

| # | Critério (chave JSON) | 1 (ruim) | 5 (ótimo) |
|---|---|---|---|
| 1 | Socrático / não entrega a solução (`socratic`) | Reescreve o código pronto | Dá o empurrão, o aluno ainda pensa |
| 2 | Ensina o porquê (`why`) | Só aponta o erro | Explica o motivo/conceito |
| 3 | Economia de palavras (`concision`) | Prolixo, textão | Conciso e direto |
| 4 | Relevância ao trecho (`relevance`) | Genérico/fora de contexto | Específico ao código |
| 5 | Corretude técnica (`correctness`) | Conselho errado/enganoso | Tecnicamente correto |

Veredito do juiz: `{"scores": {"socratic": n, "why": n, "concision": n, "relevance": n,
"correctness": n}, "rationale": "..."}`. `rubric.py` valida 5 chaves, inteiros 1-5; tolera texto
em volta do JSON. Veredito malformado → item registrado como inválido (não trava a corrida).
Agregação: média por critério + global, por modelo.

## 8. Gate de decisão (veredito de promoção)

Decisão **conjunta** — todos os portões precisam passar:

| Portão | Trilha | Critério | Racional |
|---|---|---|---|
| G0 — Formato | 0 | ≥ 95% JSON válido no probe set | Sanidade |
| G1 — Lift pedagógico | 1 + 2 | A/B: wins > losses **e** média global da rubrica ≥ base | Melhor que o ponto de partida, sem piorar |
| G2 — Sem regressão de código | 3 | pass@1(ft) ≥ pass@1(base) − ε (ε = 5 pp) | Não "esqueceu de programar" |
| G3 — Seletividade | 0/skip | Acerta ≥ metade dos casos "deve calar" | Não vira um tagarela |

**Veredito:** `PROMOVER` só se G0 ∧ G1 ∧ G2 ∧ G3. Senão, `NÃO PROMOVER` + qual portão falhou
(input acionável para a B2). Limiares (95%, ε=5pp, "wins > losses") são constantes configuráveis
em `score.py`; a primeira rodada calibra. **A B1 mede e recomenda; a troca em produção é ato da B3.**

## 9. Tratamento de erro

Natureza **oposta** ao runtime do Professor: a régua **falha alto e claro** (não fail-quiet),
mas não descarta a corrida por um item ruim.

- **Item individual ruim** (veredito malformado, geração vazia, timeout): registra como
  `inválido`/`erro` e **continua**; o relatório mostra a contagem de inválidos por trilha.
- **API do Claude falha:** retry com backoff (poucas tentativas); se persistir, a trilha do juiz
  **aborta com erro visível**. Trilhas que não dependem do Claude (formato, regressão) ainda produzem resultado.
- **Ollama fora / modelo inexistente:** erro imediato e claro.
- **Sandbox HumanEval:** cada execução isolada, com timeout (código de LLM pode ter loop
  infinito); estouro = falha daquele problema, não trava a suíte.
- **Reprodutibilidade:** seeds fixas onde há aleatoriedade (ordem do A/B, amostragem); probe set
  e subset HumanEval fixos e versionados; temperatura baixa na geração/juiz.
- **Custo/segurança da API:** volume pequeno (~40 probes × poucas trilhas × poucos modelos); o
  orquestrador loga o nº de chamadas ao Claude antes de disparar; flags permitem rodar uma trilha
  por vez (ex.: formato+regressão sem gastar API).

## 10. Testes

- **Partes puras (pytest, sem rede/GPU):**
  - `probes` — rejeita probe sem campo; valida `should_skip`; o arquivo real carrega e tem ≥ N itens.
  - `rubric` — parseia veredito válido; rejeita nota fora de 1-5, chave faltando, JSON sujo; médias.
  - `abtest` — montagem cega determinística (seed); de-anonimização correta; win/lose/tie.
  - `score` — dado resultados sintéticos das 4 trilhas, computa cada portão e o veredito
    (PROMOVER só com G0∧G1∧G2∧G3); bordas (empate A/B, regressão na margem de ε).
- **Glue (lógica pura + mock):** `judge` testado com `asker` mockado devolvendo vereditos canned;
  `runners`/`codegen` separam prompt-build (puro) da chamada Ollama; `sandbox` testa pass/fail
  com resultados de execução simulados.
- **E2E manual (a prova real):** rodar `run_eval.py` contra o `professor-ft` atual **e** o
  `qwen2.5-coder:14b` base → relatório lado a lado das 4 trilhas + veredito. Esse primeiro
  relatório calibra os limiares e entrega o baseline pedagógico que o dry-run não mediu.

## 11. Hardware / execução

- Geração de dicas e HumanEval via **Ollama local** (4080) — o 14B é lento, então o subset
  HumanEval (~35) e o probe set (~40) mantêm a corrida em minutos, não horas.
- Juiz via **Claude API** — requer chave; volume pequeno. (Reusar a config de API do ambiente.)
- Sandbox HumanEval roda no **WSL** (mesmo ambiente Python da Fatia A serve), execução isolada
  com timeout.

## 12. Questões em aberto

- Tamanho exato do probe set (~30-50) e do subset HumanEval (~35) — calibrar na 1ª rodada pelo
  tempo de corrida do 14B no Ollama.
- Modelo-juiz exato (qual Claude) e parâmetros (temperatura baixa) — fixar no plano.
- Como passar a chave da API do Claude ao harness (env var) — definir no plano, sem hardcode.
- Se a regressão de código deve gerar com greedy (temp 0) para reprodutibilidade do pass@1.
