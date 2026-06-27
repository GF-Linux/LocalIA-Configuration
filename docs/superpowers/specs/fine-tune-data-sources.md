# Professor — Fontes de dados para fine-tune (referência para a fatia futura)

Pesquisa feita em 2026-06-26. Objetivo: ver o que já existe **pronto** para fine-tunar
um modelo local (Qwen2.5-Coder / Qwen3) a gerar código E se comportar como o Professor,
em vez de gerar tudo do zero. Conclusão: **a parte de geração de código tem dados prontos
e permissivos; o comportamento de professor (no nosso formato/PT) é o nosso diferencial e
não existe pronto.**

> Esta é a **fase de fine-tune**, que vem DEPOIS do RAG (Fatia 2). Documento de referência,
> não um plano de execução ainda.

## Datasets prontos — geração de código

| Dataset | Tamanho | Licença | Observação |
|---|---|---|---|
| [nvidia/OpenCodeInstruct](https://huggingface.co/datasets/nvidia/OpenCodeInstruct) | **5M** pares | **CC BY 4.0** ✅ | Melhor opção: comercial OK (só atribuição), com testes unitários + julgamento de qualidade embutidos, gerado pela NVIDIA (sem ressalva de ToS da OpenAI). Campos: `input`/`output`/`domain`/`unit_tests`/`average_test_score`. |
| [ise-uiuc/Magicoder-OSS-Instruct-75K](https://huggingface.co/datasets/ise-uiuc/Magicoder-OSS-Instruct-75K) + Evol-Instruct-110K | 75K + 110K | permissiva, **mas** gerado de modelos OpenAI ⚠️ | Alta qualidade; atenção aos termos da OpenAI ao usar os dados/modelos. |
| CodeAlpaca / Code Instructions 120k (Alpaca) | ~20K / 120K | permissivas | Clássicos, formato Alpaca (instruction/input/output); tarefas de debug, geração, refactor. |

## Comportamento de professor — NÃO existe pronto (nosso moat)

Não há dataset drop-in com o formato do Professor (`comment/why/nudge/suggestion` +
`structure/next`, em **português**, fundamentado no nosso StackOverflow). É exatamente o que
o pipeline "RAG como fábrica de dados + destilação via Claude" produz (ver o spec da Fatia 2
e a conversa sobre fine-tune).

**Receita validada por pesquisa** (úteis como referência, dados não liberados / research-grade):
- [GuideLM — Pedagogical LLMs for Computing Education](https://arxiv.org/pdf/2411.01765) —
  tutor socrático para iniciantes, "economia de palavras", **não dar a solução pronta**.
  528 pares pergunta-aluno/resposta-tutor.
- [SFT LLMs as Pedagogical Agents in Programming Education](https://arxiv.org/abs/2502.20527) —
  fine-tune deslocou o modelo para **+8% orientação socrática** e **+58% economia de palavras**
  vs GPT-4o. **Prova que fine-tune conserta a "forma"** (não os fatos — isso é RAG).
- [ConvoLearn](https://arxiv.org/html/2601.08950v1) — diálogo tutor-aluno construtivista
  (domínio Earth Science, não código), QLoRA desloca comportamento para "knowledge-building".

## Harness de treino — pronto

- **Unsloth Qwen2.5-Coder (14B) QLoRA** — notebooks prontos, 2-5x mais rápido, ~70% menos VRAM,
  cabe na 4080 16GB, exporta GGUF para o Ollama. Templates ChatML/ShareGPT/Alpaca.
  https://unsloth.ai/blog/qwen-coder

## Estratégia recomendada (camadas) para a fatia de fine-tune

1. **Base de código:** amostra do **OpenCodeInstruct** (CC BY 4.0) → competência bruta em código.
2. **Camada professor (o diferencial):** destilar exemplos no formato do Professor
   (PT + fonte do SO + schema), gerados via Claude/RAG-em-produção. Começar com a assinatura
   do usuário (Claude Code, esta sessão) para ~200-500 exemplos de ouro; escalar via API se preciso.
3. **Harness:** Unsloth Qwen2.5-Coder QLoRA na 4080.
4. **Receita/estilo:** socrático + economia de palavras (GuideLM / SFT pedagogical agents).
5. **Avaliar:** held-out + LLM-as-judge + checagem de regressão (não declarar vitória sem medir).

## O que continua local / independente

O Professor **rodando** é 100% local (Ollama). Os datasets/destilação são bootstrap **único**;
depois do fine-tune o comportamento fica "assado" nos pesos. Modelos pagos só no bootstrap.
