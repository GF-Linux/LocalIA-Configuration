# Professor — Fine-tune Fatia A: dry-run de-risco (Design)

- **Data:** 2026-06-27
- **Status:** Design aprovado em conversa; aguardando revisão deste documento antes do plano.
- **Autor:** juaredbr + Claude
- **Depende de:** RAG (Fatia 2) implementado e no ar — é a futura fábrica de dados.
- **Referência:** `docs/superpowers/specs/fine-tune-data-sources.md` (fontes e tese).

## 1. Visão

Provar o **pipeline inteiro de fine-tune ponta a ponta** com um dataset minúsculo, antes de
investir dias num dataset grande. Sucesso do dry-run = um modelo QLoRA treinado que **carrega
no Ollama e emite o JSON do Professor válido**. Não é "ficar bom" ainda — é "o cano não vaza".

Tese (decidida nas conversas anteriores): RAG ≠ fine-tune (fatos vs comportamento); o RAG é a
fábrica de dados do fine-tune; o comportamento de professor é o diferencial (moat) e não existe
pronto; a competência de código vem de dados prontos (OpenCodeInstruct, CC BY 4.0).

## 2. Decisões confirmadas (na conversa)

1. **Alvo:** comportamento de professor **+** base de código (combinado) — mas "base de código"
   = **amostra curada** do OpenCodeInstruct como replay/âncora, **não** os 5M.
2. **Modelo base:** **Qwen2.5-Coder-14B**. O modelo fine-tunado **vira o cérebro do Professor**
   (depois aponta-se `professor.model` para o novo GGUF no Ollama). Fallback: 7B se o 14B não
   couber na 4080 — troca só o nome do modelo base, sem reescrever o pipeline.
3. **Estratégia:** **dry-run pequeno primeiro** (este spec), depois dataset cheio (Fatia B).
4. **Harness:** Unsloth QLoRA 4-bit na RTX 4080 16GB.
5. **Sementes de professor:** fabricadas via Claude Code (assinatura do usuário) como parte da
   execução, no schema real do Professor, em PT.

## 3. Escopo do dry-run (YAGNI)

NO escopo:
- **Só dicas** (não panorama) — valida o caminho principal.
- **~60 sementes de professor** (fabricadas via Claude Code) + **~300 amostras do
  OpenCodeInstruct** (CC BY 4.0) → ~360 exemplos.
- **1 época**, treino de minutos.
- **Critério de sucesso binário:** o GGUF (a) carrega no Ollama via Modelfile **e** (b) produz
  JSON `{comment,why,nudge,suggestion}` parseável num punhado de trechos de teste.

FORA do escopo (vai para a Fatia B / cheia):
- Dataset grande; colheita de exemplos reais da produção do RAG.
- Panorama (`structure/next`) no dataset.
- Avaliação séria (LLM-as-judge, regressão de código, held-out grande).
- A troca definitiva do `professor.model` em produção.

## 4. Arquitetura (6 unidades, testáveis isoladas)

```
fine-tune/
 1. data-prep   → coleta + normaliza exemplos
      • sementes de professor: JSONL no schema {code,lang,sources?,hint}
      • OpenCodeInstruct: baixa uma amostra (~300), mapeia input/output
 2. formatter   → converte tudo para ChatML, ESPELHANDO o prompt real do Professor
      (system = instrução tutor; user = código(+fontes); assistant = JSON da dica)
 3. trainer     → script Unsloth QLoRA 4-bit (Qwen2.5-Coder-14B), 1 época   [4080]
 4. exporter    → adapter LoRA → merge → GGUF (q4_k_m)
 5. ollama-load → Modelfile a partir do GGUF → `ollama create professor-ft`
 6. smoke-eval  → roda N trechos de teste pelo modelo; conta quantos dão JSON-schema válido
```

Princípio: data-prep e formatter são **Python puro testável** (sem GPU); trainer/exporter/load
são scripts executados na 4080; smoke-eval é Python que chama o Ollama local.

## 5. Decisão-chave de formato

Os exemplos de treino **espelham exatamente o prompt de runtime** do Professor — o mesmo
`system` (instrução de tutor, em PT, pedindo o JSON), o mesmo `user` (código + trechos do SO
quando houver) e o `assistant` sendo a saída JSON `{comment,why,nudge,suggestion[,source]}`.
Assim o fine-tune ensina **a tarefa real**, não uma aproximação. (Reusar o texto do
`groundedPromptBuilder` da Fatia 2 como base do system, para não divergir.)

Formato físico: **ChatML** (templates do Unsloth para Qwen2.5-Coder).

## 6. Dados

- **Sementes de professor (~60):** fabricadas via Claude Code, cada uma = um trecho de código
  com um ponto de aprendizado + a dica ideal no JSON do Professor, em PT. Curadas à mão
  (qualidade > quantidade). Misturar casos com e sem `source`, e alguns `{skip:true}` (ensinar
  seletividade — calar quando não há o que ensinar).
- **OpenCodeInstruct (~300):** amostra do dataset (CC BY 4.0), campos `input`/`output`,
  mapeados para o mesmo formato ChatML (system genérico de "responda a tarefa de código";
  estes NÃO usam o schema JSON do Professor — são a camada de competência/anti-esquecimento).
  Atribuição CC BY registrada no README do `fine-tune/`.
- **Split:** ~85% treino / ~15% held-out (mesmo no dry-run, para o smoke-eval rodar em
  exemplos não vistos).

## 7. Hardware / execução

- Treino e Ollama **competem pela VRAM** da 4080 (16GB). O `qwen2.5-coder-14b` em QLoRA 4-bit
  é apertado; o Ollama segurando um 14B (9.3GB) brigaria. Por isso o pipeline **descarrega os
  modelos do Ollama antes de treinar** (`ollama stop` / esvaziar a VRAM).
- Máquina em modo idle, só processos de servidor — confirmado pelo usuário.
- **Spill para RAM** é aceito pelo usuário (custo: muito mais lento). O dry-run **revela** se
  cabe na VRAM ou faz spill; se o 14B for inviável, o fallback documentado é o 7B (mesmo
  pipeline, outro nome de modelo).
- `OLLAMA_MODELS` recomendado em `D:` (já na nota do acervo-llm).

## 8. Tratamento de erro

- Cada etapa falha **alto e cedo** (é um pipeline de build, não runtime de produção): se o
  formatter gerar ChatML inválido, ou o trainer estourar VRAM, ou o GGUF não carregar — para e
  reporta. O dry-run existe justamente para expor esses pontos.
- `data-prep`/`formatter` validam o schema de entrada/saída e abortam em exemplo malformado.

## 9. Testes

- **data-prep, formatter:** Python puro com pytest — entrada conhecida → ChatML esperado;
  schema inválido → erro; mapeamento OpenCodeInstruct correto; split determinístico.
- **trainer/exporter/ollama-load:** validados por execução manual na 4080 (não há como
  unit-testar GPU/Ollama de forma barata) — o critério é o smoke-eval passar.
- **smoke-eval:** script que roda os trechos held-out pelo modelo via Ollama e conta JSON
  válido; testável com um mock do cliente Ollama para a lógica de contagem/parse.

## 10. Critério de pronto (dry-run)

1. `data-prep` + `formatter` produzem um JSONL ChatML válido (testes verdes).
2. `trainer` roda 1 época na 4080 sem erro (ou revela o spill/fallback 7B).
3. `exporter` gera um GGUF; `ollama-load` cria `professor-ft` no Ollama.
4. `smoke-eval`: o modelo emite JSON-schema do Professor válido em ≥ metade dos trechos
   held-out. (Qualidade pedagógica NÃO é avaliada aqui — é Fatia B.)

## 11. Próxima fatia (B — fora deste spec)

Dataset cheio: milhares de exemplos (sementes + colheita da produção do RAG via API se preciso)
+ amostra robusta do OpenCodeInstruct + panorama; avaliação séria (LLM-as-judge com rubrica,
regressão de código tipo HumanEval, held-out grande, A/B cego vs base); e a troca de
`professor.model` em produção só após lift medido sem regressão.

## 12. Questões em aberto

- Versão exata do Qwen2.5-Coder-14B no Unsloth (base vs instruct como ponto de partida do
  QLoRA) — confirmar no plano contra a model card do Unsloth.
- Tamanho de contexto do treino (~2048 provável na 4080) — o dry-run calibra.
- Quantização final do GGUF (`q4_k_m` como padrão) — confirmar compatibilidade com o Ollama.
