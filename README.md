# Professor — tutor de código proativo e local

Um tutor de programação que roda **100% local** na tua GPU (via Ollama) dentro do
VSCode. Enquanto você escreve, em checkpoints naturais (pausa de digitação / salvar),
ele observa o trecho recente e mostra uma **dica didática** — o *quê*, o *porquê* e um
empurrão pra você mesmo ajustar — num painel lateral 🎓. Ensina na prática, sem fazer
o trabalho por você.

> Fatia 1 (MVP): geração local com Qwen3 14B. O retrieval offline do StackOverflow
> entra na Fatia 2.

## Pré-requisitos

- [Ollama](https://ollama.com) rodando, com o modelo baixado:
  ```
  ollama pull qwen3:14b
  ```
- VSCode 1.90+.

## Como usar

1. Instale a extensão (`.vsix`) e recarregue o VSCode.
2. Abra o painel **Professor** (ícone 🎓 na barra de atividades).
3. Programe normalmente. Ao pausar ~1,5s ou salvar, a dica aparece no painel.

Comandos (Ctrl+Shift+P):
- **Professor: Comentar agora** — força uma dica no trecho atual.
- **Professor: Alternar mudo** — silencia/reativa o tutor.

## Configuração (`professor.*`)

| Chave | Padrão | O quê |
|---|---|---|
| `ollamaUrl` | `http://localhost:11434` | endpoint do Ollama |
| `model` | `qwen3:14b` | modelo do tutor |
| `cooldownSeconds` | `20` | intervalo mínimo entre dicas |
| `debounceMs` | `1500` | pausa de digitação que dispara a análise |
| `maxContextLines` | `30` | linhas de contexto enviadas ao modelo |
| `muted` | `false` | inicia mudo |

## Arquitetura

Lógica pura e testada em `src/core/` (gatilho, contexto, prompt, parse, render —
sem dependência do VSCode); cola fina do editor em `src/panel.ts`, `src/watcher.ts`,
`src/extension.ts`. 24 testes unitários.

## Desenvolvimento

```
npm install
npm test          # vitest
npm run compile   # esbuild -> dist/extension.js
```
Pressione `F5` para abrir um host de desenvolvimento do VSCode com a extensão carregada.

## Licença

MIT.
