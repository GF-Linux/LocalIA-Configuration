# STATE — Professor Tutor (handoff p/ nova sessão)

> Última atualização: 2026-06-27. Escrito para continuar o projeto após reiniciar o Claude Code.
> Leia também o ledger detalhado: `.superpowers/sdd/progress.md` e a memória em `~/.claude/.../memory/`.

## O que é o projeto
Extensão VSCode "Professor": tutor de código proativo e local (Ollama). Já implementado:
- **Fatia 1** (MVP local, dicas via Ollama) e **Fatia 2** (RAG StackOverflow + intenção + panorama) — código na raiz (`src/`).
- **Fine-tune Fatia A (dry-run)** — pipeline QLoRA validado: treinou Qwen2.5-Coder-14B, exportou GGUF, criou `professor-ft` no Ollama, smoke-eval 6/6. Detalhes nas memórias.
- **Fine-tune Fatia B** decomposta em B1 (régua de avaliação) → B2 (fábrica de dados) → B3 (treino em escala + troca em produção).

## Branch atual e git
- Branch de trabalho: **`feat/finetune-b1-eval`** (15 commits sobre a base do dry-run `98fd90b`).
- Base dele: `feat/finetune-dryrun`, que tem **PR #1 aberto → master** (https://github.com/juaredbr-cpu/professor-tutor/pull/1). Repo é privado no GitHub (`juaredbr-cpu/professor-tutor`), remote `origin` configurado.
- B1 NÃO foi mergeado nem teve PR — mantido as-is por decisão do usuário (esperar o baseline ao vivo antes de integrar).
- `gh` CLI instalado em `C:\Program Files\GitHub CLI\gh.exe`, autenticado como `juaredbr-cpu`.
- Nota: `.vscodeignore` aparece modificado no git status desde antes — não é nosso, deixar quieto.

## B1 — régua de avaliação (COMPLETO, revisado)
Pacote `eval/` espelhando `fine-tune/`. 9 tasks implementadas por subagentes (TDD), cada uma revisada (spec + qualidade); revisão final de branch inteira (opus) **limpa, sem bug que inverta o veredito**. **51 testes pytest verdes.**

Mede 4 trilhas e emite veredito PROMOVER/NAO_PROMOVER:
- **T0 formato**: % de dicas com JSON do schema do Professor válido (+ seletividade: calou nos probes triviais?).
- **T1 qualidade** (juiz Claude `claude-opus-4-8`): rubrica 1-5 em 5 critérios (socratic/why/concision/relevance/correctness). SÓ probes ensináveis (não-skip).
- **T2 A/B cego vs base**: Claude escolhe a melhor dica às cegas; tally ft vs base.
- **T3 regressão de código**: gera soluções HumanEval-subset (35 problemas) via Ollama, roda no sandbox, pass@1.
- **Gate**: PROMOVER só se G0(formato≥0.95) ∧ G1(A/B wins>losses E rubrica≥base) ∧ G2(código ft≥base−0.05) ∧ G3(seletividade≥0.5). Limiares em `eval/evallib/score.py` (calibráveis após o 1º baseline).

Arquivos-chave em `eval/`:
- `evallib/contract.py` (reusa is_valid_hint/TUTOR_SYSTEM/extract_json de `fine-tune/ftlib`), `probes.py`, `rubric.py`, `abtest.py`, `score.py`, `judge.py` (Claude), `runners.py` (T0), `codegen.py`+`sandbox.py` (T3).
- `data/probes.jsonl` (40 probes curados, INDEPENDENTES do treino; 32 ensináveis / 8 skip), `data/humaneval_subset.txt` (HumanEval/0..34).
- `run_eval.py` (orquestrador). venv em `eval/.venv` (anthropic==0.69.0, datasets==2.20.0, pytest==8.2.0).

### Como rodar a régua
- Testes: de `eval/` → `.venv/Scripts/python -m pytest -q` (51 passam).
- Eval só grátis (T0+T3, sem API): `.venv/Scripts/python run_eval.py --ft professor-ft --base qwen3:14b --no-judge`
- Eval completo (com juiz, ~$1): `.venv/Scripts/python run_eval.py --ft professor-ft --base qwen3:14b` (precisa de ANTHROPIC_API_KEY no ambiente).

## RESULTADO DO BASELINE AO VIVO (--no-judge) — ✅ RODOU (2026-06-27)
> STATUS: **SUCESSO.** Veredito NAO_PROMOVER, mas SÓ porque `--no-judge` reprova G1 por
> padrão (T1/T2 não rodam sem a API). Os 3 gates que rodaram (G0/G2/G3) PASSARAM.
>
> ### Números reais (probe set independente, 40 probes; código HumanEval/0..34):
> | Trilha                         | professor-ft | base (qwen2.5-coder:14b) | Gate          |
> |--------------------------------|--------------|--------------------------|---------------|
> | T0 formato (JSON válido)       | **0.97**     | 1.00                     | G0 ✅ (≥0.95) |
> | T3 código pass@1               | **0.83**     | 0.77                     | G2 ✅          |
> | Seletividade (calar no trivial)| **7/8**      | —                        | G3 ✅ (≥0.5)  |
> | T1 rubrica / T2 A/B            | não rodou    | não rodou                | G1 ❌ (default)|
>
> Leituras: (1) SEM regressão de código — ft até melhor (0.83 vs 0.77), QLoRA não causou
> esquecimento. (2) Seletividade boa (calou em 7/8 triviais). (3) Formato 0.97 vs base 1.00:
> 1 das 40 dicas do ft saiu com JSON inválido — acima do gate mas é ponto fraco a mirar no B2.
> Relatório salvo em `eval/reports/last.json`.
>
> ### Fixes aplicados nesta sessão (já no working tree, NÃO commitados):
> - `eval/evallib/runners.py` + `eval/evallib/codegen.py`: timeout 180→600s (cold-load 14B).
> - `eval/run_eval.py`: `load_dataset("openai_humaneval")` → `"openai/openai_humaneval"`
>   (huggingface_hub novo exige id namespaced; o nome canônico legado quebrou o T3).
>
> ### PRÓXIMO: eval COMPLETO com juiz (T1+T2) p/ veredito real — CONFIRMAR custo (~$1):
>    `cd eval; .venv/Scripts/python run_eval.py --ft professor-ft --base qwen2.5-coder:14b`
>    (ANTHROPIC_API_KEY já visível após reinício). Gera relatório lado a lado + veredito real.

## RESULTADO DO EVAL COMPLETO (com juiz Claude) — ✅ PROMOVER (2026-06-27)
> STATUS: **SUCESSO TOTAL. Veredito = PROMOVER. Os 4 gates passaram.** ~104 chamadas
> ao `claude-opus-4-8` (juiz). Relatório em `eval/reports/last.json`.
>
> | Trilha                          | professor-ft | base (qwen2.5-coder:14b) | Gate          |
> |---------------------------------|--------------|--------------------------|---------------|
> | T0 formato (JSON válido)        | 0.975        | 1.00                     | G0 ✅          |
> | T1 rubrica qualidade (1-5)      | **3.70**     | 1.73                     | G1 ✅          |
> | T2 A/B cego (de 39 decididos)   | **24 wins**  | 5 wins (10 empates)      | G1 ✅          |
> | T3 código pass@1                | **0.83**     | 0.77                     | G2 ✅          |
> | Seletividade (calar no trivial) | 7/8          | —                        | G3 ✅          |
>
> CONCLUSÃO: o fine-tune DOMINA em qualidade pedagógica (rubrica 2×+ a do base; A/B 24 vs 5)
> SEM regredir em código (até melhor). A régua B1 validou o fine-tune do dry-run. O único
> ponto fraco é formato 0.975 vs 1.00 do base (1 dica em 40 com JSON inválido) → alvo do B2.
>
> Pós-B1 FEITO nesta sessão (2026-06-27): (a) fixes commitados (0e850ae timeout+dataset);
> (b) gate calibrado p/ "vitória clara" (a03dc10): G1 win-rate≥0.60 E rubrica≥base+0.30;
> G3≥0.60; G0/G2 mantidos; 55 testes verdes; run real continua PROMOVER com folga;
> (c) integração: **PR #2 aberto** (base=feat/finetune-dryrun, 17 commits, empilhado sobre
> o PR #1). NÃO mergear o #2 antes do #1. Branch dryrun sincronizado no origin (+2 docs).
>
> EM ABERTO: planejar B2 (fábrica de dados) — próximo passo desta sessão.

## B2 — FÁBRICA DE DADOS (COMPLETO, 2026-06-28) — ✅
> Branch **`feat/finetune-b2-datafactory`**. Spec + plano em `docs/superpowers/specs|plans/2026-06-28-finetune-fatiaB2-datafactory*`.
> Pacote novo `fine-tune/datagen/` (9 tasks TDD por subagentes + review final opus + 2 fix waves). 78 testes verdes.
>
> **Motor:** GLM 5.2 via OpenRouter (`z-ai/glm-5.2`, OpenAI-compat) gera dica/panorama sobre código real
> (code_search_net, 6 langs); QA = juiz Claude da B1. Schema-gated (100% JSON válido).
> **Dataset gerado (commitado, 09bec9c):** `data/generated_hints.jsonl` (892 dicas) + `data/generated_panorama.jsonl` (1117).
> `build_dataset` (estendido) → **`train.jsonl` 2014 / `heldout.jsonl` 356 = 2370 exemplos** (6.5× os 361 do dry-run).
> **QA (juiz Claude, amostra 30):** rubrica **4.18/5** (acima do incumbente professor-ft 3.70; base 1.73).
> `reports/datagen.json` com contagens/QA/custo. **GLM real ~$3.85** (preço calibrado $0.95 in / $3.00 out por Mtok).
>
> ### Fatos operacionais não óbvios (importam p/ B3 e re-runs):
> - `OPENROUTER_API_KEY` no ambiente (igual ANTHROPIC). **Reasoning do GLM:** OFF é ~17× mais rápido/4× barato
>   MAS baixa qualidade (3.89 vs 4.43); o dataset final usou **`--reasoning --max-tokens 2048`** (qualidade).
> - **`anthropic==0.69.0` instalado no `fine-tune/.venv`** (a QA reusa o juiz da B1; antes só existia no eval/.venv).
> - Dataset HF exige id **namespaced**: `code-search-net/code_search_net` (legado `code_search_net` quebra).
> - Escala é **concorrente (--workers) + persistência incremental** (append+flush por linha, crash-safe/retomável,
>   dedup pré-geração). Comandos: `python -m datagen.run_datagen --kind hint|panorama --budget N --reasoning --max-tokens 2048 --workers 12 --qa 30`.
> - **B2 termina aqui.** Treinar com `train.jsonl`, rodar a régua B1 e (se PROMOVER) trocar produção = **B3**.
> - MINOR conhecido: worker cospe traceback em erro não-retryável (ex.: 402 sem crédito) — funciona (dados salvos) mas feio.

<!-- FIM_RESULTADOS -->

## Ambiente / hardware (fatos não óbvios)
- Host: **15.7 GB RAM total**, **RTX 4080 16 GB VRAM**, Windows 11. `.wslconfig` dá 12GB RAM + 32GB swap (no D:) ao WSL2.
- Fine-tune roda em **WSL2 Ubuntu 26.04**, venv `/home/jared/ft-venv` (Python 3.12, unsloth + torch cu128). Rodar comandos WSL via PowerShell (Git Bash mela paths /mnt/c). Scripts: `fine-tune/wsl_*.sh`.
- Export do GGUF do 14B estoura RAM+C: → redirecionado pro **D:** (ver `fine-tune/wsl_export.sh`). GGUF final: `D:\professor-ft-out_gguf\qwen2.5-coder-14b-instruct.Q4_K_M.gguf`.
- Ollama (Windows) ativo em :11434. Modelos presentes: **professor-ft:latest** (fine-tune), qwen3:14b (incumbente, MAS tem thinking → ruim como base p/ a régua: causou o crash por timeout), qwen2.5-coder:1.5b-base, qwen2.5vl:7b, nomic-embed-text. **Base de comparação correto = `qwen2.5-coder:14b` (precisa `ollama pull`)** — é o base real do fine-tune, instruct/JSON-friendly, sem thinking.
- **ANTHROPIC_API_KEY**: setada PERMANENTE nas variáveis de sistema (setx). Terminais novos a enxergam. O Claude Code precisa ser REINICIADO para que os processos-filho das ferramentas a enxerguem (por isso o reinício).

## PRÓXIMOS PASSOS (em ordem)
1. **Rodar o baseline --no-judge com o base correto** (ver seção RESULTADO acima): `ollama pull qwen2.5-coder:14b` e depois `cd eval; .venv/Scripts/python run_eval.py --ft professor-ft --base qwen2.5-coder:14b --no-judge`. Dá os primeiros números reais: JSON-validade do professor-ft no probe set independente, seletividade, pass@1 de código. (A 1ª tentativa com base qwen3:14b crashou por thinking+timeout.)
2. **Rodar o eval COMPLETO com juiz** (T1+T2). Após reiniciar, a chave fica visível → `cd eval; .venv/Scripts/python run_eval.py --ft professor-ft --base qwen2.5-coder:14b`. Custo ~$1 (usuário tem ~$20). Gera `eval/reports/last.json` + relatório lado a lado + veredito. CONFIRMAR com o usuário antes de gastar API.
3. **Calibrar limiares** do gate em `score.py` à luz do 1º relatório real (95% / ε=5pp / wins>losses são pontos de partida).
4. **Decidir integração do B1** (merge/PR) com a evidência do baseline em mãos (skill finishing-a-development-branch).
5. **Planejar B2 (fábrica de dados)** — brainstorming → spec → plano. Os números do B1 (onde o fine-tune está fraco) orientam que dados gerar. Ideia já registrada: gerar dados em volume via **GLM 5.2 via API** (barato) + colheita do RAG + amostra OpenCodeInstruct; incluir panorama. Ver memória `finetune-data-gen-glm`.

## Minor findings do B1 deixados para limpeza futura (não bloqueiam)
- `eval/` sem `conftest.py`/config → `pytest` da raiz do repo falha import (funciona rodando de `eval/`).
- `import json` não usado em `eval/tests/test_rubric.py`.
- `score_format` (runners.py) conta valid sobre hints sem zip a probes (mismatch latente; orquestrador sempre passa listas iguais); sem teste total==0.
- `run_eval.py` usa caminho relativo `data/probes.jsonl` (roda de `eval/`).
- Sem cutoff operacional (<50% formato pula juiz); sem teste de integração ligando saídas reais a compute_gates (usa _PASS sintético).

## Skills/processo usados
- Execução do plano: `superpowers:subagent-driven-development` (1 implementer + 1 reviewer por task; fix waves; review final). Ledger: `.superpowers/sdd/progress.md`.
- Para continuar implementação use a mesma skill; specs/planos em `docs/superpowers/specs|plans/2026-06-27-finetune-fatiaB1-*`.
