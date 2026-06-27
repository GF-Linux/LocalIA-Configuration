# Fatia 2 — Plano B: Integração na extensão (RAG + intenção + panorama) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a extensão Professor fundamentar cada dica no StackOverflow (via o serviço do Plano A), calibrar pela intenção da sessão (Projeto/Treino/Livre), e oferecer um Panorama (estrutura + próximo passo) periódico — tudo no painel.

**Architecture:** Estende a extensão da Fatia 1. Novos módulos puros (queryExtractor, retrievalClient, groundedPromptBuilder, outline, panorama) testados com vitest; a cola fina (watcher/extension/panel) só orquestra. A dica passa a: extrair query (qwen2.5-coder:1.5b) → buscar no serviço → prompt fundamentado → Qwen3 14B → painel com fonte. O Panorama dispara ao salvar/comando.

**Tech Stack:** TypeScript, VSCode Extension API, Node fetch, Ollama (qwen3:14b + qwen2.5-coder:1.5b), vitest, esbuild.

## Global Constraints

- 100% local; o único serviço externo é o retrieval-service do Plano A (LAN/Tailscale), URL configurável (`professor.retrievalUrl`, default `http://localhost:8765`).
- **Sempre fundamentar:** toda dica passa pela busca. Se a busca falhar/vier vazia → degrada para o modo Fatia 1 (ensina sem fonte); **nunca quebra**.
- Nunca bloquear a digitação; toda chamada assíncrona e descartável (mantém AbortController + fail-quiet da Fatia 1).
- A query do StackOverflow é gerada em **inglês** (o `.zim` é inglês), mesmo o ensino sendo em PT.
- **Dois modelos, só um pesado:** query via `qwen2.5-coder:1.5b` (rápido) com fallback heurístico; ensino via `qwen3:14b` (uma vez).
- Contratos de tipo (consistentes com o servidor e a Fatia 1):
  - `RetrievalResult = { title: string; url: string; snippet: string }`
  - `Hint` (estende a Fatia 1) `= { comment, why, nudge, suggestion?, source?: { title: string; url: string } }`
  - `Panorama = { structure: string; next: string }`
  - `Intent = "projeto" | "treino" | "livre"`
- Intenção persistida em `workspaceState` (chave `professor.intent`); perguntada uma vez se ausente; comando para mudar.
- Panorama é separado/periódico: dispara ao salvar e por comando, com cooldown próprio.
- Reaproveitamento: `ollamaClient.askOllama` (Fatia 1) já aceita `model`/`timeoutMs` — reutilizar para o modelo pequeno.

---

### Task 1: Estender o schema — `source` no Hint + `RetrievalResult`

**Files:**
- Modify: `src/core/responseParser.ts`
- Test: `src/core/responseParser.test.ts`
- Create: `src/core/types.ts`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `src/core/types.ts`: `export type RetrievalResult = { title: string; url: string; snippet: string }`
  - `Hint` (em responseParser.ts) ganha `source?: { title: string; url: string }`; `parseHint` aceita `source` opcional (se objeto com `title`/`url` strings).

- [ ] **Step 1: Write the failing test**

Adicione a `src/core/responseParser.test.ts`:
```ts
it("inclui source quando presente e válido", () => {
  const h = parseHint('{"comment":"c","why":"w","nudge":"n","source":{"title":"T","url":"U"}}');
  expect(h).toEqual({ comment: "c", why: "w", nudge: "n", source: { title: "T", url: "U" } });
});

it("ignora source inválido", () => {
  expect(parseHint('{"comment":"c","why":"w","nudge":"n","source":{"title":"T"}}'))
    .toEqual({ comment: "c", why: "w", nudge: "n" });
  expect(parseHint('{"comment":"c","why":"w","nudge":"n","source":"x"}'))
    .toEqual({ comment: "c", why: "w", nudge: "n" });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- responseParser`
Expected: FAIL — `source` não é incluído.

- [ ] **Step 3: Create types.ts and extend parseHint**

`src/core/types.ts`:
```ts
export type RetrievalResult = { title: string; url: string; snippet: string };
```

Em `src/core/responseParser.ts`, estenda o tipo e o parse. Substitua o tipo `Hint` e o final de `parseHint`:
```ts
export type Hint = {
  comment: string;
  why: string;
  nudge: string;
  suggestion?: string;
  source?: { title: string; url: string };
};
```
E, logo antes de `return hint;` (depois do bloco que adiciona `suggestion`), acrescente:
```ts
  const s = obj.source;
  if (s && typeof s.title === "string" && typeof s.url === "string") {
    hint.source = { title: s.title, url: s.url };
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- responseParser`
Expected: PASS (testes anteriores + 2 novos).

- [ ] **Step 5: Commit**

```bash
git add src/core/types.ts src/core/responseParser.ts src/core/responseParser.test.ts
git commit -m "feat(fatia2): add optional source to Hint + RetrievalResult type"
```

---

### Task 2: queryExtractor — código → query de busca (puro)

**Files:**
- Create: `src/core/queryExtractor.ts`
- Test: `src/core/queryExtractor.test.ts`

**Interfaces:**
- Consumes: `EditorContext` (Fatia 1, `contextCollector`), `ChatMessage` (Fatia 1, `promptBuilder`).
- Produces:
  - `buildQueryMessages(ctx: EditorContext): ChatMessage[]` — pede ao modelo pequeno uma query de busca curta em INGLÊS, só palavras-chave.
  - `cleanQuery(raw: string): string` — limpa a resposta do modelo (primeira linha, sem aspas/pontuação, ≤ 12 palavras).
  - `heuristicQuery(code: string, lang: string): string` — fallback: extrai identificadores/keywords do código + a linguagem.

- [ ] **Step 1: Write the failing test**

`src/core/queryExtractor.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { buildQueryMessages, cleanQuery, heuristicQuery } from "./queryExtractor";

describe("buildQueryMessages", () => {
  const msgs = buildQueryMessages({ code: "f = open('x')", lang: "python", file: "a.py" });
  it("system pede query curta em inglês, só palavras-chave", () => {
    const s = msgs[0].content.toLowerCase();
    expect(s).toContain("english");
    expect(s).toContain("search");
  });
  it("user inclui o código", () => {
    expect(msgs[1].content).toContain("f = open('x')");
  });
});

describe("cleanQuery", () => {
  it("tira aspas e limita palavras", () => {
    expect(cleanQuery('"python read file with open"')).toBe("python read file with open");
  });
  it("pega só a primeira linha", () => {
    expect(cleanQuery("python open file\nextra junk")).toBe("python open file");
  });
  it("limita a 12 palavras", () => {
    const q = cleanQuery("a b c d e f g h i j k l m n o");
    expect(q.split(" ").length).toBe(12);
  });
});

describe("heuristicQuery", () => {
  it("extrai identificadores + linguagem", () => {
    const q = heuristicQuery("conteudo = open('dados.txt').read()", "python");
    expect(q).toContain("python");
    expect(q.toLowerCase()).toContain("open");
  });
  it("não estoura com código vazio", () => {
    expect(heuristicQuery("", "python")).toBe("python");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- queryExtractor`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/queryExtractor.ts`:
```ts
import type { EditorContext } from "./contextCollector";
import type { ChatMessage } from "./promptBuilder";

const SYSTEM = `You turn a code snippet into a SHORT StackOverflow search query in ENGLISH.
Output ONLY the query: keywords/API/error terms, no quotes, no sentence, max 12 words.`;

export function buildQueryMessages(ctx: EditorContext): ChatMessage[] {
  return [
    { role: "system", content: SYSTEM },
    { role: "user", content: `Language: ${ctx.lang}\nCode:\n${ctx.code}` },
  ];
}

export function cleanQuery(raw: string): string {
  const firstLine = raw.split("\n")[0] ?? "";
  const noQuotes = firstLine.replace(/["'`]/g, " ").replace(/\s+/g, " ").trim();
  return noQuotes.split(" ").filter(Boolean).slice(0, 12).join(" ");
}

export function heuristicQuery(code: string, lang: string): string {
  const ids = (code.match(/[A-Za-z_][A-Za-z0-9_]{2,}/g) ?? [])
    .filter((w, i, a) => a.indexOf(w) === i)
    .slice(0, 6);
  return [lang, ...ids].join(" ").trim();
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- queryExtractor`
Expected: PASS (7 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/queryExtractor.ts src/core/queryExtractor.test.ts
git commit -m "feat(fatia2): query extractor (prompt + cleaner + heuristic fallback)"
```

---

### Task 3: retrievalClient — HTTP ao serviço (fail-quiet)

**Files:**
- Create: `src/core/retrievalClient.ts`
- Test: `src/core/retrievalClient.test.ts`

**Interfaces:**
- Consumes: `RetrievalResult` (Task 1).
- Produces:
  - `fetchRetrieval(query: string, opts: { url: string; k: number; signal?: AbortSignal; timeoutMs?: number }): Promise<RetrievalResult[]>` — GET `${url}/retrieve?q=&k=`; **fail-quiet**: qualquer erro/HTTP não-ok/JSON inválido → `[]`.

- [ ] **Step 1: Write the failing test**

`src/core/retrievalClient.test.ts`:
```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchRetrieval } from "./retrievalClient";

const opts = { url: "http://localhost:8765", k: 3 };
afterEach(() => vi.restoreAllMocks());

describe("fetchRetrieval", () => {
  it("GET /retrieve com q e k, devolve a lista", async () => {
    const data = [{ title: "T", url: "U", snippet: "S" }];
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
    vi.stubGlobal("fetch", fetchMock);
    const out = await fetchRetrieval("python open", opts);
    expect(out).toEqual(data);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/retrieve?");
    expect(url).toContain("q=python%20open");
    expect(url).toContain("k=3");
  });
  it("HTTP não-ok → []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    expect(await fetchRetrieval("x", opts)).toEqual([]);
  });
  it("erro de rede → []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    expect(await fetchRetrieval("x", opts)).toEqual([]);
  });
  it("JSON não-lista → []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }));
    expect(await fetchRetrieval("x", opts)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- retrievalClient`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/retrievalClient.ts`:
```ts
import type { RetrievalResult } from "./types";

export async function fetchRetrieval(
  query: string,
  opts: { url: string; k: number; signal?: AbortSignal; timeoutMs?: number }
): Promise<RetrievalResult[]> {
  const timeoutMs = opts.timeoutMs ?? 5000;
  const signal = opts.signal
    ? AbortSignal.any([opts.signal, AbortSignal.timeout(timeoutMs)])
    : AbortSignal.timeout(timeoutMs);
  const url = `${opts.url}/retrieve?q=${encodeURIComponent(query)}&k=${opts.k}`;
  try {
    const res = await fetch(url, { signal });
    if (!res.ok) return [];
    const data: unknown = await res.json();
    return Array.isArray(data) ? (data as RetrievalResult[]) : [];
  } catch {
    return [];
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- retrievalClient`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/retrievalClient.ts src/core/retrievalClient.test.ts
git commit -m "feat(fatia2): retrieval client (HTTP, fail-quiet)"
```

---

### Task 4: groundedPromptBuilder — prompt fundamentado + intenção (puro)

**Files:**
- Create: `src/core/intent.ts`
- Create: `src/core/groundedPromptBuilder.ts`
- Test: `src/core/groundedPromptBuilder.test.ts`

**Interfaces:**
- Consumes: `EditorContext`, `ChatMessage`, `RetrievalResult` (Task 1).
- Produces:
  - `src/core/intent.ts`: `export type Intent = "projeto" | "treino" | "livre"`; `export function intentClause(intent: Intent | undefined): string` (frase curta para calibrar o system prompt).
  - `buildGroundedTutorMessages(ctx: EditorContext, sources: RetrievalResult[], intent: Intent | undefined): ChatMessage[]` — instrui o modelo a ensinar fundamentado nos trechos do SO, em PT, e preencher `source` com a melhor fonte usada; se `sources` vazio, ensina sem fonte (degradação).

- [ ] **Step 1: Write the failing test**

`src/core/groundedPromptBuilder.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { buildGroundedTutorMessages } from "./groundedPromptBuilder";
import { intentClause } from "./intent";

const ctx = { code: "open('f')", lang: "python", file: "f.py" };
const sources = [{ title: "Reading files", url: "questions/123", snippet: "use with open()" }];

describe("intentClause", () => {
  it("calibra por intenção", () => {
    expect(intentClause("treino").toLowerCase()).toContain("fundament");
    expect(intentClause("projeto").toLowerCase()).toContain("estrutura");
    expect(intentClause(undefined)).toBe("");
  });
});

describe("buildGroundedTutorMessages", () => {
  it("system pede JSON com source e ensino em PT", () => {
    const s = buildGroundedTutorMessages(ctx, sources, "treino")[0].content.toLowerCase();
    expect(s).toContain("json");
    expect(s).toContain("source");
    expect(s).toContain("portugu");
  });
  it("user inclui os trechos do StackOverflow quando há fontes", () => {
    const u = buildGroundedTutorMessages(ctx, sources, undefined)[1].content;
    expect(u).toContain("use with open()");
    expect(u).toContain("Reading files");
    expect(u).toContain("open('f')");
  });
  it("sem fontes: não inventa seção de fontes, ainda ensina", () => {
    const u = buildGroundedTutorMessages(ctx, [], undefined)[1].content;
    expect(u).toContain("open('f')");
    expect(u.toLowerCase()).not.toContain("stackoverflow:");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- groundedPromptBuilder`
Expected: FAIL — módulos não existem.

- [ ] **Step 3: Write minimal implementation**

`src/core/intent.ts`:
```ts
export type Intent = "projeto" | "treino" | "livre";

export function intentClause(intent: Intent | undefined): string {
  switch (intent) {
    case "projeto":
      return "O aluno trabalha num PROJETO real: valorize estrutura, organização e manutenção.";
    case "treino":
      return "O aluno está em TREINO: foque em fundamentos e no idioma correto, bem fundamentado.";
    case "livre":
      return "O aluno explora LIVREMENTE: seja leve, comente só o essencial.";
    default:
      return "";
  }
}
```

`src/core/groundedPromptBuilder.ts`:
```ts
import type { EditorContext } from "./contextCollector";
import type { ChatMessage } from "./promptBuilder";
import type { RetrievalResult } from "./types";
import { intentClause, type Intent } from "./intent";

const BASE = `Você é um professor de programação que ensina na prática, em português do Brasil.
Ensine UM ponto de aprendizado relevante, fundamentado nos trechos do StackOverflow quando houver.
Regras:
- Ensine o PORQUÊ e o idioma correto; NÃO reescreva todo o código (dê um empurrão).
- Em "suggestion", um trecho CURTO de código idiomático (só as linhas relevantes).
- Em "source", repita {title,url} da fonte do StackOverflow que você usou (omita se não usou nenhuma).
- Se não houver nada que valha a pena ensinar, responda exatamente {"skip": true}.
Responda SOMENTE em JSON válido:
{"comment":"...","why":"...","nudge":"...","suggestion":"...","source":{"title":"...","url":"..."}}  ou  {"skip": true}`;

export function buildGroundedTutorMessages(
  ctx: EditorContext,
  sources: RetrievalResult[],
  intent: Intent | undefined
): ChatMessage[] {
  const clause = intentClause(intent);
  const system = clause ? `${BASE}\n${clause}` : BASE;
  let user = `Linguagem: ${ctx.lang}\nArquivo: ${ctx.file}\nCódigo recente:\n\`\`\`${ctx.lang}\n${ctx.code}\n\`\`\``;
  if (sources.length > 0) {
    const blocks = sources
      .map((s) => `- ${s.title} (${s.url})\n  ${s.snippet}`)
      .join("\n");
    user += `\n\nTrechos do StackOverflow:\n${blocks}`;
  }
  return [
    { role: "system", content: system },
    { role: "user", content: user },
  ];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- groundedPromptBuilder`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/intent.ts src/core/groundedPromptBuilder.ts src/core/groundedPromptBuilder.test.ts
git commit -m "feat(fatia2): grounded tutor prompt + intent calibration"
```

---

### Task 5: outline — esqueleto do arquivo (puro)

**Files:**
- Create: `src/core/outline.ts`
- Test: `src/core/outline.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `extractOutline(text: string, maxLines?: number): string` — se o arquivo tem ≤ `maxLines` (default 120) linhas, devolve o texto inteiro; senão devolve só as linhas "estruturais" (imports + linhas que começam com `def`/`class`/`function`/`export`/`const`/`import`/`from`, ignorando indentação interna profunda), juntas.

- [ ] **Step 1: Write the failing test**

`src/core/outline.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { extractOutline } from "./outline";

describe("extractOutline", () => {
  it("arquivo pequeno: devolve tudo", () => {
    const text = "import os\n\ndef a():\n    return 1";
    expect(extractOutline(text, 120)).toBe(text);
  });
  it("arquivo grande: só linhas estruturais", () => {
    const body = Array.from({ length: 200 }, (_, i) => `    x = ${i}`).join("\n");
    const text = `import os\nclass Foo:\n${body}\ndef bar():\n${body}`;
    const out = extractOutline(text, 120);
    expect(out).toContain("import os");
    expect(out).toContain("class Foo:");
    expect(out).toContain("def bar():");
    expect(out).not.toContain("x = 150");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- outline`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/outline.ts`:
```ts
const STRUCT = /^\s*(import |from |export |def |class |function |const |public |private )/;

export function extractOutline(text: string, maxLines = 120): string {
  const lines = text.split("\n");
  if (lines.length <= maxLines) return text;
  return lines.filter((l) => STRUCT.test(l)).join("\n");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- outline`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/outline.ts src/core/outline.test.ts
git commit -m "feat(fatia2): file outline extraction for panorama"
```

---

### Task 6: panorama — prompt + parser (puro)

**Files:**
- Create: `src/core/panorama.ts`
- Test: `src/core/panorama.test.ts`

**Interfaces:**
- Consumes: `ChatMessage`, `Intent` (Task 4).
- Produces:
  - `type Panorama = { structure: string; next: string }`.
  - `buildPanoramaMessages(outline: string, lang: string, intent: Intent | undefined): ChatMessage[]`.
  - `parsePanorama(raw: string): Panorama | null` — `null` em skip/JSON inválido/campos faltando (fail-quiet, igual `parseHint`).

- [ ] **Step 1: Write the failing test**

`src/core/panorama.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { buildPanoramaMessages, parsePanorama } from "./panorama";

describe("buildPanoramaMessages", () => {
  const msgs = buildPanoramaMessages("class Foo:\ndef bar():", "python", "projeto");
  it("system pede structure e next em JSON, PT", () => {
    const s = msgs[0].content.toLowerCase();
    expect(s).toContain("structure");
    expect(s).toContain("next");
    expect(s).toContain("portugu");
  });
  it("user inclui o outline", () => {
    expect(msgs[1].content).toContain("class Foo:");
  });
});

describe("parsePanorama", () => {
  it("parseia panorama completo", () => {
    expect(parsePanorama('{"structure":"s","next":"n"}')).toEqual({ structure: "s", next: "n" });
  });
  it("skip → null", () => {
    expect(parsePanorama('{"skip": true}')).toBeNull();
  });
  it("JSON inválido → null", () => {
    expect(parsePanorama("nope")).toBeNull();
  });
  it("campo faltando → null", () => {
    expect(parsePanorama('{"structure":"s"}')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- panorama`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/panorama.ts`:
```ts
import type { ChatMessage } from "./promptBuilder";
import { intentClause, type Intent } from "./intent";

export type Panorama = { structure: string; next: string };

const BASE = `Você é um professor de programação, em português do Brasil. Olhe o ESQUELETO do
arquivo do aluno e dê uma visão de PANORAMA: a estrutura/organização e o próximo passo.
Regras:
- "structure": uma observação curta sobre organização/arquitetura (ou o que falta).
- "next": o próximo passo concreto / para onde isso vai.
- Se o arquivo é trivial demais para um panorama, responda exatamente {"skip": true}.
Responda SOMENTE em JSON válido: {"structure":"...","next":"..."}  ou  {"skip": true}`;

export function buildPanoramaMessages(
  outline: string,
  lang: string,
  intent: Intent | undefined
): ChatMessage[] {
  const clause = intentClause(intent);
  const system = clause ? `${BASE}\n${clause}` : BASE;
  return [
    { role: "system", content: system },
    { role: "user", content: `Linguagem: ${lang}\nEsqueleto do arquivo:\n${outline}` },
  ];
}

export function parsePanorama(raw: string): Panorama | null {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start === -1 || end <= start) return null;
  let obj: any;
  try {
    obj = JSON.parse(raw.slice(start, end + 1));
  } catch {
    return null;
  }
  if (obj && obj.skip === true) return null;
  if (obj && typeof obj.structure === "string" && typeof obj.next === "string") {
    return { structure: obj.structure, next: obj.next };
  }
  return null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- panorama`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/panorama.ts src/core/panorama.test.ts
git commit -m "feat(fatia2): panorama prompt + parser"
```

---

### Task 7: Painel em duas seções — render de fonte + panorama (puro + provider)

**Files:**
- Modify: `src/core/renderHint.ts`
- Test: `src/core/renderHint.test.ts`
- Modify: `src/panel.ts`
- Modify: `media/panel.css`

**Interfaces:**
- Consumes: `Hint` (Task 1, com `source`), `Panorama` (Task 6).
- Produces:
  - `renderHintHtml(hint: Hint | null, muted: boolean)` — agora renderiza a 📚 fonte quando `hint.source` existe.
  - `renderPanoramaHtml(panorama: Panorama | null): string` — seção "Panorama" (estrutura + próximo passo), ou vazio se `null`.
  - `ProfessorViewProvider.update(hint, force)` mantém a dica; novo `updatePanorama(panorama: Panorama | null): void` atualiza a 2ª seção. O HTML do painel passa a ter duas seções empilhadas (dica em cima, panorama embaixo).

- [ ] **Step 1: Write the failing test (render puro)**

Adicione a `src/core/renderHint.test.ts`:
```ts
import { renderPanoramaHtml } from "./renderHint";

it("renderiza a fonte do StackOverflow quando há source", () => {
  const html = renderHintHtml(
    { comment: "c", why: "w", nudge: "n", source: { title: "Reading files", url: "questions/1" } },
    false
  );
  expect(html).toContain("📚");
  expect(html).toContain("Reading files");
});

it("escapa HTML da fonte (XSS)", () => {
  const html = renderHintHtml(
    { comment: "c", why: "w", nudge: "n", source: { title: "<script>x</script>", url: "u" } },
    false
  );
  expect(html).not.toContain("<script>x");
});

it("renderPanoramaHtml mostra structure e next", () => {
  const html = renderPanoramaHtml({ structure: "S1", next: "N1" });
  expect(html).toContain("S1");
  expect(html).toContain("N1");
});

it("renderPanoramaHtml vazio quando null", () => {
  expect(renderPanoramaHtml(null)).toBe("");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- renderHint`
Expected: FAIL — `renderPanoramaHtml` não existe / fonte não renderiza.

- [ ] **Step 3: Extend renderHint.ts**

Em `src/core/renderHint.ts`, adicione import do tipo e duas mudanças. No topo:
```ts
import type { Panorama } from "./panorama";
```
Dentro de `renderHintHtml`, logo após montar `suggestion`, adicione:
```ts
  const source = hint.source
    ? `<div class="source">📚 <a href="#">${esc(hint.source.title)}</a></div>`
    : "";
```
E inclua `${source}` no template, após `${suggestion}`. Depois, ao fim do arquivo:
```ts
export function renderPanoramaHtml(panorama: Panorama | null): string {
  if (!panorama) return "";
  return `
    <div class="panorama">
      <div class="pano-title">🗺️ Panorama</div>
      <div class="structure"><b>Estrutura:</b> ${esc(panorama.structure)}</div>
      <div class="next"><b>Próximo:</b> ${esc(panorama.next)}</div>
    </div>`;
}
```

- [ ] **Step 4: Run render tests**

Run: `npm test -- renderHint`
Expected: PASS (testes anteriores + 4 novos).

- [ ] **Step 5: Update the panel provider for two sections**

Em `src/panel.ts`: adicione um campo `private panorama: Panorama | null = null;` e importe `renderPanoramaHtml` + `Panorama`. Adicione o método:
```ts
  updatePanorama(panorama: Panorama | null): void {
    this.panorama = panorama;
    this.render(this.lastHintForRender);
  }
```
Guarde a última dica num campo (`private lastHintForRender: Hint | null = null;`) e, em `update`/`render`, persista-a. No `render`, troque o corpo do `<body>` para empilhar as duas seções:
```ts
    const body = `${renderHintHtml(hint, this.muted)}${renderPanoramaHtml(this.panorama)}`;
    this.view.webview.html = `<!DOCTYPE html><html><head>
      <meta charset="utf-8">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${this.view.webview.cspSource};">
      <link rel="stylesheet" href="${cssUri}"></head>
      <body>${body}</body></html>`;
```
(Mantenha o guard de `muted` que decide se renderiza a dica; o panorama não é silenciado pelo mudo — é uma seção separada.)

- [ ] **Step 6: Add CSS for the new sections**

Adicione a `media/panel.css`:
```css
.hint .source { margin-top: 8px; opacity: 0.85; font-size: 0.9em; }
.panorama { margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--vscode-widget-border, rgba(127,127,127,0.3)); }
.panorama .pano-title { font-weight: bold; margin-bottom: 6px; }
.panorama .structure, .panorama .next { margin-top: 4px; opacity: 0.95; }
```

- [ ] **Step 7: Compile**

Run: `npm run compile`
Expected: sem erros de tipo; gera `dist/extension.js`.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(fatia2): two-section panel (source citation + panorama)"
```

---

### Task 8: Intenção — armazenamento + comando + pergunta no painel

**Files:**
- Create: `src/intentStore.ts`
- Modify: `src/panel.ts` (estado vazio oferece a pergunta de intenção)
- Modify: `package.json` (comando `professor.setIntent`)

**Interfaces:**
- Consumes: `Intent` (Task 4).
- Produces:
  - `src/intentStore.ts`: `getIntent(context: vscode.ExtensionContext): Intent | undefined` e `setIntent(context, intent): Thenable<void>` (lê/grava `workspaceState` chave `"professor.intent"`).
  - Comando `professor.setIntent` que mostra um QuickPick (Projeto/Treino/Livre) e persiste.

- [ ] **Step 1: Write the intent store + command (no automated test — vscode glue)**

`src/intentStore.ts`:
```ts
import * as vscode from "vscode";
import type { Intent } from "./core/intent";

const KEY = "professor.intent";

export function getIntent(context: vscode.ExtensionContext): Intent | undefined {
  return context.workspaceState.get<Intent>(KEY);
}

export function setIntent(context: vscode.ExtensionContext, intent: Intent): Thenable<void> {
  return context.workspaceState.update(KEY, intent);
}

export async function promptIntent(context: vscode.ExtensionContext): Promise<Intent | undefined> {
  const pick = await vscode.window.showQuickPick(
    [
      { label: "Projeto", value: "projeto" as Intent },
      { label: "Treino", value: "treino" as Intent },
      { label: "Livre", value: "livre" as Intent },
    ],
    { placeHolder: "O que você está fazendo aqui? (calibra o Professor)" }
  );
  if (pick) await setIntent(context, pick.value);
  return pick?.value;
}
```

- [ ] **Step 2: Add the command to package.json**

Em `package.json`, dentro de `"commands"`, acrescente:
```json
{ "command": "professor.setIntent", "title": "Professor: Definir intenção (Projeto/Treino/Livre)" }
```

- [ ] **Step 3: Compile (type-check the vscode glue)**

Run: `npm run compile`
Expected: sem erros.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(fatia2): session intent store + setIntent command"
```

---

### Task 9: Fiação completa (watcher com RAG + panorama + comandos/config) — E2E

**Files:**
- Modify: `src/watcher.ts`
- Modify: `src/extension.ts`
- Modify: `package.json` (config `retrievalUrl`, `queryModel`, `panoramaCooldownSeconds`; comando `professor.panorama`)

**Interfaces:**
- Consumes: tudo das tarefas anteriores + Fatia 1 (`askOllama`, `extractContext`, `decideTrigger`, `parseHint`, `ProfessorViewProvider`).
- Produces: extensão Fatia 2 funcional ponta a ponta.

- [ ] **Step 1: Add config + command to package.json**

Em `"configuration".properties`, acrescente:
```json
"professor.retrievalUrl": { "type": "string", "default": "http://localhost:8765" },
"professor.queryModel": { "type": "string", "default": "qwen2.5-coder:1.5b" },
"professor.panoramaCooldownSeconds": { "type": "number", "default": 60 }
```
Em `"commands"`, acrescente:
```json
{ "command": "professor.panorama", "title": "Professor: Panorama (estrutura + próximo passo)" }
```

- [ ] **Step 2: Update the hint flow in watcher.ts to ground via retrieval**

Em `src/watcher.ts`, importe os novos módulos:
```ts
import { buildQueryMessages, cleanQuery, heuristicQuery } from "./core/queryExtractor";
import { fetchRetrieval } from "./core/retrievalClient";
import { buildGroundedTutorMessages } from "./core/groundedPromptBuilder";
import { extractOutline } from "./core/outline";
import { buildPanoramaMessages, parsePanorama } from "./core/panorama";
import { getIntent } from "./intentStore";
```
O `Watcher` precisa do `ExtensionContext` (para a intenção). Mude o construtor para `constructor(private readonly panel: ProfessorViewProvider, private readonly context: vscode.ExtensionContext) {}`.

No `analyzeNow`, **substitua a montagem do prompt + chamada** (o trecho que hoje faz `askOllama(buildTutorMessages(ctx), ...)`) por: extrair query (modelo pequeno, com fallback heurístico se falhar/vier vazio) → buscar no serviço → prompt fundamentado → Qwen3:
```ts
    const intent = getIntent(this.context);
    // 1) query de busca (modelo pequeno, fail-quiet → heurística)
    let query = "";
    try {
      const raw = await askOllama(buildQueryMessages(ctx), {
        url: cfg.get<string>("ollamaUrl", "http://localhost:11434"),
        model: cfg.get<string>("queryModel", "qwen2.5-coder:1.5b"),
        timeoutMs: 20000,
        signal: this.abort.signal,
      });
      query = cleanQuery(raw);
    } catch { /* cai no fallback abaixo */ }
    if (!query) query = heuristicQuery(ctx.code, ctx.lang);
    // 2) busca no StackOverflow (fail-quiet → [])
    const sources = await fetchRetrieval(query, {
      url: cfg.get<string>("retrievalUrl", "http://localhost:8765"),
      k: 3,
      signal: this.abort.signal,
    });
    // 3) ensino fundamentado
    const raw = await askOllama(buildGroundedTutorMessages(ctx, sources, intent), {
      url: cfg.get<string>("ollamaUrl", "http://localhost:11434"),
      model: cfg.get<string>("model", "qwen3:14b"),
      timeoutMs: cfg.get<number>("timeoutSeconds", 120) * 1000,
      signal: this.abort.signal,
    });
    this.panel.update(parseHint(raw), force);
```
(Mantenha o `try/except` externo de fail-safe da Fatia 1 ao redor de tudo isso, e o aviso de erro só no caminho `force`.)

Adicione um método de panorama com cooldown próprio:
```ts
  private lastPanoramaMs = -Infinity;

  async panoramaNow(force = false): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    const cfg = this.cfg();
    const cd = cfg.get<number>("panoramaCooldownSeconds", 60) * 1000;
    if (!force && Date.now() - this.lastPanoramaMs < cd) return;
    this.lastPanoramaMs = Date.now();
    const outline = extractOutline(editor.document.getText());
    if (!outline.trim()) return;
    try {
      const raw = await askOllama(
        buildPanoramaMessages(outline, editor.document.languageId, getIntent(this.context)),
        {
          url: cfg.get<string>("ollamaUrl", "http://localhost:11434"),
          model: cfg.get<string>("model", "qwen3:14b"),
          timeoutMs: cfg.get<number>("timeoutSeconds", 120) * 1000,
        }
      );
      this.panel.updatePanorama(parsePanorama(raw));
    } catch { /* fail-quiet */ }
  }
```

- [ ] **Step 3: Wire the new constructor arg, commands, save-trigger, intent prompt in extension.ts**

Em `src/extension.ts`:
- Passe o contexto ao watcher: `const watcher = new Watcher(panel, context);`
- No listener de salvar (que já existe), além de `watcher.schedule()`, dispare o panorama: `void watcher.panoramaNow();` (respeita o cooldown).
- Registre os comandos:
```ts
    vscode.commands.registerCommand("professor.panorama", () => void watcher.panoramaNow(true)),
    vscode.commands.registerCommand("professor.setIntent", async () => {
      const { promptIntent } = await import("./intentStore");
      await promptIntent(context);
    }),
```
- Pergunta de intenção uma vez: na ativação, se `getIntent(context)` for `undefined`, ofereça (sem bloquear): `void (async () => { const { promptIntent } = await import("./intentStore"); await promptIntent(context); })();` — ou deixe para a primeira dica. (Escolha simples: oferecer na ativação se ausente.)

- [ ] **Step 4: Run the full unit suite**

Run: `npm test`
Expected: PASS — todos os testes puros (Fatia 1 + Tasks 1-7 da Fatia 2).

- [ ] **Step 5: Compile**

Run: `npm run compile`
Expected: sem erros de tipo; gera `dist/extension.js`.

- [ ] **Step 6: Manual E2E — dica fundamentada (precisa do serviço do Plano A no ar)**

Pré-requisitos: `ollama serve` com `qwen3:14b` e `qwen2.5-coder:1.5b`; o retrieval-service (Plano A) rodando e alcançável na `professor.retrievalUrl`.
1. `F5` (host de desenvolvimento) ou empacotar+instalar o `.vsix`.
2. Defina a intenção (comando "Professor: Definir intenção" → Treino).
3. Em `teste.py`, digite o `open()` sem `with`; pause.
Expected: a dica aparece **com uma 📚 fonte** do StackOverflow (título). Se o serviço estiver desligado, a dica ainda aparece (sem fonte) — degradação graciosa.

- [ ] **Step 7: Manual E2E — panorama**

1. Salve o arquivo (Ctrl+S) ou rode "Professor: Panorama".
Expected: a seção 🗺️ Panorama aparece embaixo, com Estrutura + Próximo passo, calibrada pela intenção.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(fatia2): wire RAG hint flow + panorama + intent/commands/config (E2E)"
```

---

## Notas de execução

- **Pré-requisitos:** o serviço do Plano A precisa estar rodando para o E2E fundamentado (Steps 6-7); os testes unitários (Tasks 1-8) não precisam.
- **Modelo pequeno:** `qwen2.5-coder:1.5b` já está instalado (confirmado). A query é a única chamada a ele; falha → heurística.
- **Degradação graciosa:** se o retrieval-service estiver fora, `fetchRetrieval` devolve `[]` e a dica vira modo Fatia 1 (sem fonte) — sem quebrar.
- **Fora de escopo (anotar):** abrir a fonte do SO ao clicar (precisaria de um kiwix-serve no servidor) — hoje o link é decorativo; RAG vetorial (bge-m3) é fatia futura.
- **Reaproveitamento:** `askOllama` (Fatia 1) já suporta `model`/`timeoutMs`/`signal` — usado tanto para o modelo pequeno (query) quanto para o 14B (ensino/panorama).
