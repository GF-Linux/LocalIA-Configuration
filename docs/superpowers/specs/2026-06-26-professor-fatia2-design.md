# Professor — Fatia 2: fundamentação no StackOverflow + intenção + panorama (Design)

- **Data:** 2026-06-26
- **Status:** Design aprovado em conversa (decisões-chave confirmadas); aguardando revisão deste documento antes do plano.
- **Autor:** juaredbr + Claude
- **Depende de:** Fatia 1 (MVP local, já implementado e instalado).

## 1. Visão

Elevar a qualidade das dicas do Professor de "modelo chutando da cabeça" para
**ensino fundamentado em respostas reais do StackOverflow** (acervo offline `.zim`
no servidor), e adicionar duas camadas de tutoria: **intenção da sessão** (o que o
aluno está construindo) e **panorama** (estrutura + continuidade no nível do projeto).

Motivação: no teste da Fatia 1 as dicas variaram (umas boas, umas ruins) porque o
modelo raciocina sobre ~30 linhas, sem fonte externa, e é meio obrigado a falar.
Fundamentar reduz o "chute"; a intenção calibra; o panorama dá o nível-projeto.

## 2. Objetivos e não-objetivos

Objetivos:
- **Toda dica local fundamentada** no StackOverflow, com citação da fonte.
- **Pergunta de intenção** (Projeto / Treino / Livre) uma vez por workspace, que
  calibra o tom e o quanto de conselho estrutural.
- **Panorama** separado e periódico (ao salvar / sob comando) com estrutura e
  próximos passos, alimentado por contexto amplo (arquivo/esqueleto) e pela intenção.
- 100% local (4080 + servidor da LAN via Tailscale). Degradação graciosa.

Não-objetivos (YAGNI):
- **Não** é RAG vetorial ainda — MVP usa **busca por palavra-chave** (full-text do
  libzim). Vetorial (bge-m3) fica para uma fatia futura.
- **Não** gera o projeto por você; o panorama orienta, não anda sozinho.
- **Não** troca o modelo de chat; segue Qwen3 14B para ensinar.

## 3. Decisões confirmadas (na conversa)

1. **Quando buscar:** sempre — toda dica local passa pela busca e é fundamentada.
2. **Tecnologia de retrieval:** Opção A — serviço Python (FastAPI + `python-libzim`)
   no servidor, devolvendo JSON limpo. (Rejeitadas: kiwix-serve+HTML por ser frágil;
   RAG vetorial por ser pesado/prematuro.)
3. **Extração da query:** modelo pequeno **qwen2.5-coder:1.5b** (já instalado, ~1s)
   transforma o código numa query de busca; assim o modelo *pesado* (14B) roda só uma
   vez, para ensinar — não dobra a latência.
4. **Estrutura/continuidade:** entregue como **Panorama separado e periódico**
   (ao salvar / comando "Professor: Panorama"), não embutido em cada dica.

## 4. Arquitetura

```
┌─ Máquina 4080 (extensão) ─────────────────────────────────────────┐
│ DICA LOCAL (ao pausar digitação):                                 │
│  1. queryExtractor: código → query de busca   ← qwen2.5-coder:1.5b │
│  2. retrievalClient: GET servidor /retrieve ──HTTP/Tailscale──┐    │
│  4. groundedPromptBuilder: código + trechos SO + intenção     │    │
│  5. askOllama (Qwen3 14B) → dica fundamentada + fonte          │    │
│  6. painel: dica + 📚 fonte                                    │    │
│                                                               │    │
│ PANORAMA (ao salvar / comando):                               │    │
│  A. outline do arquivo (imports + defs/classes) ou arquivo    │    │
│  B. panoramaPromptBuilder: outline + intenção                 │    │
│  C. askOllama (Qwen3 14B) → {structure, next}                 │    │
│  D. painel (seção Panorama)                                   │    │
│                                                               ↓    │
└────────────────────────────────────────────────────────────────────┘
┌─ Servidor (Francesca) ────────────────────────────────────────────┐
│  retrieval-service (FastAPI + python-libzim)                      │
│   GET /retrieve?q=<query>&k=3                                      │
│   → [{ title, url, snippet }]  sobre                               │
│     stackoverflow.com_en_all_2023-11.zim (80 GB)                  │
│   roda como serviço (mesmo padrão do ankivet)                     │
└────────────────────────────────────────────────────────────────────┘
```

Princípio: extensão orquestra; servidor só busca. Cada peça tem um papel e é
testável isolada.

## 5. Componentes

### Servidor (subsistema 1 — plano próprio)
1. **retrieval-service** (Python/FastAPI): abre o `.zim` com `python-libzim`, expõe
   `GET /retrieve?q=&k=` → `[{title, url, snippet}]`. Busca full-text; extrai um
   snippet curto em volta do match. Saúde em `GET /health`. Testável com `curl`.
   Motor de busca: `python-libzim` (`Query().set_query(...)` + `Searcher(zim).search(query)`
   + `search.getResults(0, n)` + `getEstimatedMatches()`). A lógica de snippet/citação
   pode ser adaptada do `llm-tools-kiwix` (Apache-2.0; é biblioteca/CLI, não servidor —
   embrulhamos numa FastAPI própria, no padrão do ankivet).

### Extensão (subsistema 2 — plano próprio)
2. **queryExtractor** (puro + 1 chamada ao modelo pequeno): código → string de busca
   curta (palavras-chave/API/erro). Prompt mínimo; fallback heurístico (identificadores)
   se o modelo pequeno falhar.
3. **retrievalClient**: HTTP ao servidor, com timeout e **fail-quiet** (erro → `[]`).
   URL configurável (`professor.retrievalUrl`).
4. **groundedPromptBuilder** (puro): monta o prompt da dica com código + trechos do SO
   + intenção. Schema da dica cresce: `source?: { title: string; url: string }`.
5. **intent** (estado + UI): `professor.intent` salvo em `workspaceState`
   (`projeto|treino|livre|undefined`). Na 1ª dica/abertura sem intenção definida, o
   painel oferece a pergunta; comando **"Professor: Definir intenção"** para mudar.
6. **outline** (puro): do texto do arquivo extrai imports + linhas de `def/class`
   (heurística por linguagem) ou o arquivo todo se < N linhas. Alimenta o panorama.
7. **panoramaPromptBuilder** (puro): outline + intenção → prompt que pede
   `{ structure, next }` (ambos curtos, em PT). Intenção calibra: "projeto" liga
   estrutura/manutenção; "treino" foca fundamentos; "livre" minimiza.
8. **panel** (cresce): duas seções empilhadas — **Dica** (com 📚 fonte) e
   **Panorama** (estrutura + próximo passo). Render puro, escapa HTML.
9. **watcher** (cresce): mantém o fluxo de dica (agora com retrieval) e adiciona o
   gatilho de panorama (ao salvar + comando), com seu próprio cooldown.

## 6. Fluxo de dados

**Dica local:** pausa → extrai query (1.5b) → `/retrieve` no servidor → prompt
fundamentado → Qwen3 14B → parse (dica + source) → painel (seção Dica).

**Panorama:** salvar/comando → outline do arquivo → prompt de panorama (com intenção)
→ Qwen3 14B → parse `{structure, next}` → painel (seção Panorama).

**Intenção:** lida do `workspaceState`; se ausente, painel mostra a pergunta antes de
fundamentar; resposta persiste por workspace.

## 7. Schema das respostas do modelo

- **Dica:** `{ comment, why, nudge, suggestion?, source? : {title, url} }` ou `{skip:true}`.
- **Panorama:** `{ structure, next }` ou `{skip:true}` (arquivo trivial → sem panorama).
- **Retrieval (servidor):** `[{ title, url, snippet }]` (vazio se nada relevante).

## 8. Tratamento de erro / degradação graciosa

- **Servidor de retrieval fora / vazio:** dica cai para o modo Fatia 1 (ensina sem
  fonte); painel sinaliza "sem fonte agora". Nunca quebra.
- **Modelo pequeno (query) falha:** usa o fallback heurístico de query.
- **Timeouts:** retrieval com timeout curto (ex.: 5s); modelo herda o
  `professor.timeoutSeconds` da Fatia 1.
- **Fail-quiet** mantido; comando explícito do usuário mostra erro (como na Fatia 1).

## 9. Testes

- **retrieval-service:** pytest/`curl` com queries conhecidas (ex.: "python read file
  with") retornando hits esperados do `.zim`; `/health`.
- **queryExtractor, outline, groundedPromptBuilder, panoramaPromptBuilder, parsers,
  render:** módulos puros com testes unitários (vitest), incluindo escape de HTML da
  fonte e do panorama.
- **retrievalClient:** fetch mockado (sucesso, vazio, erro→`[]`).
- **E2E manual:** servidor no ar + código ensinável → dica com 📚 fonte real; salvar →
  panorama coerente com a intenção.

## 10. Hardware / topologia

- Extensão + Ollama (Qwen3 14B + qwen2.5-coder:1.5b): **máquina 4080**.
- retrieval-service + `.zim` do SO: **servidor (Francesca)**, alcançado por Tailscale/LAN.

## 11. Faseamento / planos

Dois planos de implementação, um spec:
- **Plano A — retrieval-service no servidor** (Python/FastAPI/libzim). Entrega
  software testável sozinho (`curl /retrieve`).
- **Plano B — integração na extensão** (queryExtractor, retrievalClient, grounded
  prompt + source, intenção, outline, panorama, painel em duas seções).

Cada plano produz software funcionando e testável por si.

## 11b. Reaproveitamento de open-source (validado via GitHub)

| Peça | Projeto | Licença | Uso |
|---|---|---|---|
| Busca full-text no `.zim` | [python-libzim](https://github.com/openzim/python-libzim) | permissiva (openZIM) | Motor de busca do retrieval-service (`Query`/`Searcher`/`Search`) |
| Snippet/citação sobre `.zim` | [llm-tools-kiwix](https://github.com/mozanunal/llm-tools-kiwix) | Apache-2.0 | Referência de código (é lib/CLI, não servidor — embrulhar em FastAPI própria) |
| RAG vetorial (Fatia futura) | [zim-llm](https://github.com/rouralberto/zim-llm) | a confirmar | Referência da fase vetorial (MiniLM + Chroma, pré-computa embeddings) |
| Scaffold webview | vscode-extension-samples | MIT | Já usado na Fatia 1 |
| LLMs | Ollama (Qwen3 14B + qwen2.5-coder:1.5b) | — | Já instalados |

Nenhum desses é dependência de runtime "pesada": `python-libzim` é o único pip novo no
servidor; o `llm-tools-kiwix` entra como referência de código (Apache-2.0), não como
dependência. O `zim-llm` só importa quando/se formos pro RAG vetorial.

## 12. Questões em aberto

- `python-libzim` no Windows do servidor: confirmar wheel/instalação (fallback:
  kiwix-serve binário se o wheel falhar).
- Como abrir a fonte do SO ao clicar (exige um kiwix-serve para visualizar o artigo
  offline) — MVP mostra título/snippet; link clicável fica para depois.
- Idioma das queries: o `.zim` é **inglês**; o queryExtractor deve gerar a query em
  inglês mesmo o ensino sendo em PT.
- Cadência do panorama: cooldown próprio (ex.: ao salvar, no máx. 1 a cada N s).
