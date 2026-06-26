# Professor Tutor — Fatia 1 (MVP local, sem StackOverflow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uma extensão VSCode que observa o código e, em checkpoints (pausa/salvar), mostra uma dica didática gerada localmente pelo Qwen3 14B (Ollama) num painel lateral — sem StackOverflow ainda.

**Architecture:** A lógica difícil vive em módulos **puros** (sem `import vscode`), testados com vitest: política de gatilho (cooldown/dedup), extração de contexto, construção de prompt, parse da resposta, render do HTML. A cola com o VSCode (watcher de eventos, webview view, fios em `extension.ts`) é fina e validada por E2E manual. O LLM é chamado via API HTTP do Ollama em `localhost:11434`.

**Tech Stack:** TypeScript, VSCode Extension API (webview view), Node 18 `fetch`, Ollama (`qwen3:14b`), vitest, esbuild.

## Global Constraints

- 100% local; nenhuma chamada de nuvem. LLM = Ollama `qwen3:14b` em `http://localhost:11434` (configurável).
- A extensão **nunca bloqueia a digitação**: toda chamada de LLM é assíncrona e descartável.
- **Fail-quiet:** resposta inválida ou erro → painel não muda / mostra estado neutro; jamais lança erro pro usuário nem repete spam.
- Anti-irritação obrigatória: cooldown configurável + dedup por hash do trecho + botão mudo.
- Sem StackOverflow nesta fatia (a UI reserva espaço pra fonte, mas não a usa).
- Tutor responde em **português**.
- Linguagem-alvo dos testes: exemplos em Python.
- Contrato de dica entre módulos: `Hint = { comment: string; why: string; nudge: string }`; "nada a ensinar" = `null`.

---

### Task 1: Scaffold da extensão + harness de testes

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `vitest.config.ts`
- Create: `esbuild.mjs`
- Create: `.vscodeignore`
- Create: `.gitignore`
- Create: `src/extension.ts`
- Create: `src/core/version.ts`
- Test: `src/core/version.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces: `EXT_VERSION: string` (sanity), build via `npm run compile`, testes via `npm test`.

- [ ] **Step 1: Write the failing test**

`src/core/version.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { EXT_VERSION } from "./version";

describe("version", () => {
  it("expõe uma string semver", () => {
    expect(EXT_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — `Cannot find module './version'`.

- [ ] **Step 3: Create the project files**

`package.json`:
```json
{
  "name": "professor-tutor",
  "displayName": "Professor",
  "description": "Tutor de código proativo e local",
  "version": "0.1.0",
  "publisher": "juaredbr",
  "engines": { "vscode": "^1.90.0" },
  "main": "./dist/extension.js",
  "activationEvents": ["onStartupFinished"],
  "contributes": {},
  "scripts": {
    "compile": "node esbuild.mjs",
    "watch": "node esbuild.mjs --watch",
    "test": "vitest run",
    "vscode:prepublish": "node esbuild.mjs --production"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/vscode": "^1.90.0",
    "esbuild": "^0.21.0",
    "typescript": "^5.4.0",
    "vitest": "^1.6.0"
  }
}
```

`tsconfig.json`:
```json
{
  "compilerOptions": {
    "module": "Node16",
    "moduleResolution": "Node16",
    "target": "ES2022",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist"
  },
  "include": ["src"],
  "exclude": ["node_modules", "**/*.test.ts"]
}
```

`vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: { include: ["src/**/*.test.ts"], environment: "node" },
});
```

`esbuild.mjs`:
```js
import esbuild from "esbuild";
const production = process.argv.includes("--production");
const watch = process.argv.includes("--watch");
const ctx = await esbuild.context({
  entryPoints: ["src/extension.ts"],
  bundle: true,
  format: "cjs",
  platform: "node",
  outfile: "dist/extension.js",
  external: ["vscode"],
  sourcemap: !production,
  minify: production,
});
if (watch) { await ctx.watch(); } else { await ctx.rebuild(); await ctx.dispose(); }
```

`.vscodeignore`:
```
src/**
node_modules/**
**/*.test.ts
vitest.config.ts
esbuild.mjs
tsconfig.json
docs/**
```

`.gitignore`:
```
node_modules/
dist/
*.vsix
*.pdf
.vscode-test/
```

`src/core/version.ts`:
```ts
export const EXT_VERSION = "0.1.0";
```

`src/extension.ts`:
```ts
import * as vscode from "vscode";
import { EXT_VERSION } from "./core/version";

export function activate(_context: vscode.ExtensionContext): void {
  console.log(`Professor ${EXT_VERSION} ativo`);
}

export function deactivate(): void {}
```

- [ ] **Step 4: Install deps, run test to verify it passes**

Run: `npm install && npm test`
Expected: PASS (1 test).

- [ ] **Step 5: Verify it compiles**

Run: `npm run compile`
Expected: gera `dist/extension.js` sem erros.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: scaffold extension + vitest harness"
```

---

### Task 2: Política de gatilho (cooldown + dedup) — módulo puro

**Files:**
- Create: `src/core/triggerPolicy.ts`
- Test: `src/core/triggerPolicy.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `type TriggerState = { lastFiredMs: number; lastHash: string | null }`
  - `function initialTriggerState(): TriggerState`
  - `function hashCode(s: string): string`
  - `function decideTrigger(state: TriggerState, nowMs: number, codeHash: string, cooldownMs: number): { fire: boolean; nextState: TriggerState }`

- [ ] **Step 1: Write the failing test**

`src/core/triggerPolicy.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { initialTriggerState, decideTrigger, hashCode } from "./triggerPolicy";

describe("decideTrigger", () => {
  it("dispara na primeira vez", () => {
    const r = decideTrigger(initialTriggerState(), 1000, "h1", 5000);
    expect(r.fire).toBe(true);
    expect(r.nextState).toEqual({ lastFiredMs: 1000, lastHash: "h1" });
  });

  it("NÃO dispara dentro do cooldown", () => {
    const s = { lastFiredMs: 1000, lastHash: "h1" };
    expect(decideTrigger(s, 3000, "h2", 5000).fire).toBe(false);
  });

  it("NÃO dispara se o hash do código não mudou (dedup)", () => {
    const s = { lastFiredMs: 1000, lastHash: "h1" };
    expect(decideTrigger(s, 9000, "h1", 5000).fire).toBe(false);
  });

  it("dispara após cooldown se o código mudou", () => {
    const s = { lastFiredMs: 1000, lastHash: "h1" };
    const r = decideTrigger(s, 9000, "h2", 5000);
    expect(r.fire).toBe(true);
    expect(r.nextState).toEqual({ lastFiredMs: 9000, lastHash: "h2" });
  });

  it("hashCode é estável e distingue strings", () => {
    expect(hashCode("abc")).toBe(hashCode("abc"));
    expect(hashCode("abc")).not.toBe(hashCode("abd"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- triggerPolicy`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/triggerPolicy.ts`:
```ts
export type TriggerState = { lastFiredMs: number; lastHash: string | null };

export function initialTriggerState(): TriggerState {
  return { lastFiredMs: -Infinity, lastHash: null };
}

export function hashCode(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

export function decideTrigger(
  state: TriggerState,
  nowMs: number,
  codeHash: string,
  cooldownMs: number
): { fire: boolean; nextState: TriggerState } {
  const withinCooldown = nowMs - state.lastFiredMs < cooldownMs;
  const sameCode = codeHash === state.lastHash;
  if (withinCooldown || sameCode) return { fire: false, nextState: state };
  return { fire: true, nextState: { lastFiredMs: nowMs, lastHash: codeHash } };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- triggerPolicy`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/triggerPolicy.ts src/core/triggerPolicy.test.ts
git commit -m "feat: trigger policy with cooldown and dedup"
```

---

### Task 3: Extração de contexto — módulo puro

**Files:**
- Create: `src/core/contextCollector.ts`
- Test: `src/core/contextCollector.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `type EditorContext = { code: string; lang: string; file: string }`
  - `function extractContext(text: string, lang: string, file: string, cursorLine: number, maxLines?: number): EditorContext` — devolve até `maxLines` (default 30) linhas terminando na linha do cursor (inclusiva).

- [ ] **Step 1: Write the failing test**

`src/core/contextCollector.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { extractContext } from "./contextCollector";

const text = ["a=1", "b=2", "c=3", "d=4", "e=5"].join("\n");

describe("extractContext", () => {
  it("pega as últimas N linhas até o cursor", () => {
    const ctx = extractContext(text, "python", "f.py", 4, 3);
    expect(ctx.code).toBe("c=3\nd=4\ne=5");
    expect(ctx.lang).toBe("python");
    expect(ctx.file).toBe("f.py");
  });

  it("não estoura no começo do arquivo", () => {
    expect(extractContext(text, "python", "f.py", 1, 10).code).toBe("a=1\nb=2");
  });

  it("trata linha de cursor além do fim", () => {
    expect(extractContext(text, "python", "f.py", 99, 2).code).toBe("d=4\ne=5");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- contextCollector`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/contextCollector.ts`:
```ts
export type EditorContext = { code: string; lang: string; file: string };

export function extractContext(
  text: string,
  lang: string,
  file: string,
  cursorLine: number,
  maxLines = 30
): EditorContext {
  const lines = text.split("\n");
  const end = Math.min(cursorLine, lines.length); // 1-based, inclusivo
  const start = Math.max(0, end - maxLines);
  return { code: lines.slice(start, end).join("\n"), lang, file };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- contextCollector`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/contextCollector.ts src/core/contextCollector.test.ts
git commit -m "feat: editor context extraction"
```

---

### Task 4: Construção do prompt de professor — módulo puro

**Files:**
- Create: `src/core/promptBuilder.ts`
- Test: `src/core/promptBuilder.test.ts`

**Interfaces:**
- Consumes: `EditorContext` (Task 3).
- Produces:
  - `type ChatMessage = { role: "system" | "user"; content: string }`
  - `function buildTutorMessages(ctx: EditorContext): ChatMessage[]`

- [ ] **Step 1: Write the failing test**

`src/core/promptBuilder.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { buildTutorMessages } from "./promptBuilder";

describe("buildTutorMessages", () => {
  const msgs = buildTutorMessages({ code: "open('f')", lang: "python", file: "f.py" });

  it("tem system + user", () => {
    expect(msgs.map((m) => m.role)).toEqual(["system", "user"]);
  });

  it("system instrui ensino (não resolver) e JSON em português", () => {
    const s = msgs[0].content.toLowerCase();
    expect(s).toContain("professor");
    expect(s).toContain("json");
    expect(s).toContain("portugu");
    expect(s).toContain("skip");
  });

  it("user inclui o código e a linguagem", () => {
    expect(msgs[1].content).toContain("open('f')");
    expect(msgs[1].content).toContain("python");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- promptBuilder`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/promptBuilder.ts`:
```ts
import type { EditorContext } from "./contextCollector";

export type ChatMessage = { role: "system" | "user"; content: string };

const SYSTEM = `Você é um professor de programação que ensina na prática, em português do Brasil.
Olhe o trecho de código do aluno e, se houver UM ponto de aprendizado relevante, ensine.
Regras:
- Ensine o PORQUÊ e o idioma correto; NÃO reescreva todo o código por ele (dê um empurrão).
- Seja breve e específico ao trecho.
- Se não houver nada que valha a pena ensinar agora, responda exatamente {"skip": true}.
Responda SOMENTE em JSON válido, sem texto fora do JSON, no formato:
{"comment": "...", "why": "...", "nudge": "..."}  ou  {"skip": true}`;

export function buildTutorMessages(ctx: EditorContext): ChatMessage[] {
  const user = `Linguagem: ${ctx.lang}\nArquivo: ${ctx.file}\nCódigo recente:\n\`\`\`${ctx.lang}\n${ctx.code}\n\`\`\``;
  return [
    { role: "system", content: SYSTEM },
    { role: "user", content: user },
  ];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- promptBuilder`
Expected: PASS (3 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/promptBuilder.ts src/core/promptBuilder.test.ts
git commit -m "feat: tutor prompt builder"
```

---

### Task 5: Parse da resposta do modelo — módulo puro

**Files:**
- Create: `src/core/responseParser.ts`
- Test: `src/core/responseParser.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `type Hint = { comment: string; why: string; nudge: string }`
  - `function parseHint(raw: string): Hint | null` — `null` quando `skip`, JSON inválido, ou campos faltando.

- [ ] **Step 1: Write the failing test**

`src/core/responseParser.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { parseHint } from "./responseParser";

describe("parseHint", () => {
  it("parseia uma dica completa", () => {
    const h = parseHint('{"comment":"c","why":"w","nudge":"n"}');
    expect(h).toEqual({ comment: "c", why: "w", nudge: "n" });
  });

  it("aceita JSON cercado de texto/sujeira", () => {
    expect(parseHint('lixo {"comment":"c","why":"w","nudge":"n"} fim'))
      .toEqual({ comment: "c", why: "w", nudge: "n" });
  });

  it("retorna null em skip", () => {
    expect(parseHint('{"skip": true}')).toBeNull();
  });

  it("retorna null em JSON inválido", () => {
    expect(parseHint("não é json")).toBeNull();
  });

  it("retorna null se faltar campo", () => {
    expect(parseHint('{"comment":"c"}')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- responseParser`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/responseParser.ts`:
```ts
export type Hint = { comment: string; why: string; nudge: string };

export function parseHint(raw: string): Hint | null {
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
  const ok =
    obj &&
    typeof obj.comment === "string" &&
    typeof obj.why === "string" &&
    typeof obj.nudge === "string";
  return ok ? { comment: obj.comment, why: obj.why, nudge: obj.nudge } : null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- responseParser`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/responseParser.ts src/core/responseParser.test.ts
git commit -m "feat: model response parser (hint | null)"
```

---

### Task 6: Cliente Ollama

**Files:**
- Create: `src/core/ollamaClient.ts`
- Test: `src/core/ollamaClient.test.ts`

**Interfaces:**
- Consumes: `ChatMessage` (Task 4).
- Produces:
  - `function askOllama(messages: ChatMessage[], opts: { url: string; model: string; signal?: AbortSignal }): Promise<string>` — devolve `message.content`; lança `Error` em falha de rede/HTTP.

- [ ] **Step 1: Write the failing test**

`src/core/ollamaClient.test.ts`:
```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { askOllama } from "./ollamaClient";

const opts = { url: "http://localhost:11434", model: "qwen3:14b" };

afterEach(() => vi.restoreAllMocks());

describe("askOllama", () => {
  it("POSTa em /api/chat e devolve o content", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ message: { content: '{"skip":true}' } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const out = await askOllama([{ role: "user", content: "oi" }], opts);
    expect(out).toBe('{"skip":true}');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:11434/api/chat");
    const body = JSON.parse(init.body);
    expect(body.model).toBe("qwen3:14b");
    expect(body.stream).toBe(false);
    expect(body.format).toBe("json");
  });

  it("lança em HTTP não-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(askOllama([], opts)).rejects.toThrow(/500/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- ollamaClient`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write minimal implementation**

`src/core/ollamaClient.ts`:
```ts
import type { ChatMessage } from "./promptBuilder";

export async function askOllama(
  messages: ChatMessage[],
  opts: { url: string; model: string; signal?: AbortSignal }
): Promise<string> {
  const res = await fetch(`${opts.url}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: opts.model,
      messages,
      stream: false,
      format: "json",
    }),
    signal: opts.signal,
  });
  if (!res.ok) throw new Error(`Ollama HTTP ${res.status}`);
  const data: any = await res.json();
  return data?.message?.content ?? "";
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- ollamaClient`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add src/core/ollamaClient.ts src/core/ollamaClient.test.ts
git commit -m "feat: ollama chat client"
```

---

### Task 7: Painel "Professor" (render puro + WebviewViewProvider)

**Files:**
- Create: `src/core/renderHint.ts`
- Test: `src/core/renderHint.test.ts`
- Create: `src/panel.ts`
- Create: `media/panel.css`
- Modify: `package.json` (contribui view container + view)

**Interfaces:**
- Consumes: `Hint` (Task 5).
- Produces:
  - `function renderHintHtml(hint: Hint | null, muted: boolean): string` (puro)
  - `class ProfessorViewProvider implements vscode.WebviewViewProvider` com `viewType = "professor.view"` e método `update(hint: Hint | null): void`.

- [ ] **Step 1: Write the failing test (render puro)**

`src/core/renderHint.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { renderHintHtml } from "./renderHint";

describe("renderHintHtml", () => {
  it("mostra comment/why/nudge da dica", () => {
    const html = renderHintHtml({ comment: "C1", why: "W1", nudge: "N1" }, false);
    expect(html).toContain("C1");
    expect(html).toContain("W1");
    expect(html).toContain("N1");
  });

  it("estado vazio quando hint é null", () => {
    expect(renderHintHtml(null, false).toLowerCase()).toContain("observando");
  });

  it("estado mudo", () => {
    expect(renderHintHtml(null, true).toLowerCase()).toContain("mudo");
  });

  it("escapa HTML do conteúdo do modelo", () => {
    const html = renderHintHtml({ comment: "<script>x</script>", why: "w", nudge: "n" }, false);
    expect(html).not.toContain("<script>x");
    expect(html).toContain("&lt;script&gt;");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- renderHint`
Expected: FAIL — módulo não existe.

- [ ] **Step 3: Write the pure render module**

`src/core/renderHint.ts`:
```ts
import type { Hint } from "./responseParser";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function renderHintHtml(hint: Hint | null, muted: boolean): string {
  if (muted) return `<div class="empty">🔇 Professor em mudo.</div>`;
  if (!hint) return `<div class="empty">🎓 Observando seu código…</div>`;
  return `
    <div class="hint">
      <div class="comment">💡 ${esc(hint.comment)}</div>
      <div class="why"><b>Por quê:</b> ${esc(hint.why)}</div>
      <div class="nudge"><b>Tente:</b> ${esc(hint.nudge)}</div>
    </div>`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- renderHint`
Expected: PASS (4 testes).

- [ ] **Step 5: Write the WebviewViewProvider + CSS**

`media/panel.css`:
```css
body { font-family: var(--vscode-font-family); padding: 10px; color: var(--vscode-foreground); }
.empty { opacity: 0.7; font-style: italic; }
.hint .comment { font-size: 1.05em; margin-bottom: 8px; }
.hint .why, .hint .nudge { margin-top: 6px; opacity: 0.95; }
```

`src/panel.ts`:
```ts
import * as vscode from "vscode";
import { renderHintHtml } from "./core/renderHint";
import type { Hint } from "./core/responseParser";

export class ProfessorViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "professor.view";
  private view?: vscode.WebviewView;
  private muted = false;

  constructor(private readonly extensionUri: vscode.Uri) {}

  resolveWebviewView(view: vscode.WebviewView): void {
    this.view = view;
    view.webview.options = { enableScripts: false, localResourceRoots: [this.extensionUri] };
    this.render(null);
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.render(null);
  }

  update(hint: Hint | null): void {
    if (this.muted) return;
    this.render(hint);
  }

  private render(hint: Hint | null): void {
    if (!this.view) return;
    const cssUri = this.view.webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "panel.css")
    );
    this.view.webview.html = `<!DOCTYPE html><html><head>
      <link rel="stylesheet" href="${cssUri}"></head>
      <body>${renderHintHtml(hint, this.muted)}</body></html>`;
  }
}
```

- [ ] **Step 6: Contribute the view in package.json**

Substitua `"contributes": {}` em `package.json` por:
```json
"contributes": {
  "viewsContainers": {
    "activitybar": [
      { "id": "professor", "title": "Professor", "icon": "media/icon.svg" }
    ]
  },
  "views": {
    "professor": [
      { "type": "webview", "id": "professor.view", "name": "Professor" }
    ]
  }
}
```
Crie `media/icon.svg` (placeholder simples):
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="currentColor" d="M12 3 1 9l11 6 9-4.9V17h2V9L12 3zM5 13.2V17l7 3.8 7-3.8v-3.8l-7 3.8-7-3.8z"/></svg>
```

- [ ] **Step 7: Manual E2E — painel aparece**

Run: `npm run compile`, então pressione `F5` no VSCode.
Expected: na janela de desenvolvimento aparece o ícone 🎓 "Professor" na activity bar; ao abrir, mostra "Observando seu código…".

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: professor webview panel with pure render"
```

---

### Task 8: Fiação completa (watcher + comandos + config) — E2E

**Files:**
- Create: `src/watcher.ts`
- Modify: `src/extension.ts` (substituição completa)
- Modify: `package.json` (config + comandos)

**Interfaces:**
- Consumes: `decideTrigger`/`initialTriggerState`/`hashCode` (T2), `extractContext` (T3), `buildTutorMessages` (T4), `parseHint` (T5), `askOllama` (T6), `ProfessorViewProvider` (T7).
- Produces: extensão funcional ponta a ponta.

- [ ] **Step 1: Add config + commands to package.json**

Dentro de `"contributes"`, adicione ao lado de `viewsContainers`/`views`:
```json
"configuration": {
  "title": "Professor",
  "properties": {
    "professor.ollamaUrl": { "type": "string", "default": "http://localhost:11434" },
    "professor.model": { "type": "string", "default": "qwen3:14b" },
    "professor.cooldownSeconds": { "type": "number", "default": 20 },
    "professor.debounceMs": { "type": "number", "default": 1500 },
    "professor.maxContextLines": { "type": "number", "default": 30 },
    "professor.muted": { "type": "boolean", "default": false }
  }
},
"commands": [
  { "command": "professor.toggleMute", "title": "Professor: Alternar mudo" },
  { "command": "professor.commentNow", "title": "Professor: Comentar agora" }
]
```

- [ ] **Step 2: Write the watcher**

`src/watcher.ts`:
```ts
import * as vscode from "vscode";
import { TriggerState, initialTriggerState, decideTrigger, hashCode } from "./core/triggerPolicy";
import { extractContext } from "./core/contextCollector";
import { buildTutorMessages } from "./core/promptBuilder";
import { askOllama } from "./core/ollamaClient";
import { parseHint } from "./core/responseParser";
import { ProfessorViewProvider } from "./panel";

export class Watcher {
  private state: TriggerState = initialTriggerState();
  private timer: NodeJS.Timeout | undefined;
  private abort: AbortController | undefined;

  constructor(private readonly panel: ProfessorViewProvider) {}

  private cfg() {
    return vscode.workspace.getConfiguration("professor");
  }

  /** Chamado em edição/salvar; agenda uma análise com debounce. */
  schedule(): void {
    if (this.cfg().get<boolean>("muted")) return;
    if (this.timer) clearTimeout(this.timer);
    const debounce = this.cfg().get<number>("debounceMs", 1500);
    this.timer = setTimeout(() => void this.analyzeNow(), debounce);
  }

  /** Análise imediata (comando "comentar agora" ou fim do debounce). */
  async analyzeNow(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    const cfg = this.cfg();
    const ctx = extractContext(
      editor.document.getText(),
      editor.document.languageId,
      editor.document.fileName,
      editor.selection.active.line + 1,
      cfg.get<number>("maxContextLines", 30)
    );
    if (!ctx.code.trim()) return;

    const decision = decideTrigger(
      this.state,
      Date.now(),
      hashCode(ctx.code),
      cfg.get<number>("cooldownSeconds", 20) * 1000
    );
    if (!decision.fire) return;
    this.state = decision.nextState;

    this.abort?.abort();
    this.abort = new AbortController();
    try {
      const raw = await askOllama(buildTutorMessages(ctx), {
        url: cfg.get<string>("ollamaUrl", "http://localhost:11434"),
        model: cfg.get<string>("model", "qwen3:14b"),
        signal: this.abort.signal,
      });
      this.panel.update(parseHint(raw)); // null => painel fica quieto (fail-quiet)
    } catch {
      // erro de rede/Ollama: silencioso, nunca interrompe o usuário
    }
  }

  dispose(): void {
    if (this.timer) clearTimeout(this.timer);
    this.abort?.abort();
  }
}
```

- [ ] **Step 3: Rewrite extension.ts to wire everything**

`src/extension.ts` (substituição completa):
```ts
import * as vscode from "vscode";
import { ProfessorViewProvider } from "./panel";
import { Watcher } from "./watcher";

export function activate(context: vscode.ExtensionContext): void {
  const panel = new ProfessorViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(ProfessorViewProvider.viewType, panel)
  );

  const watcher = new Watcher(panel);
  context.subscriptions.push(watcher);

  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document === vscode.window.activeTextEditor?.document) watcher.schedule();
    }),
    vscode.workspace.onDidSaveTextDocument(() => watcher.schedule()),
    vscode.commands.registerCommand("professor.commentNow", () => void watcher.analyzeNow()),
    vscode.commands.registerCommand("professor.toggleMute", async () => {
      const cfg = vscode.workspace.getConfiguration("professor");
      const next = !cfg.get<boolean>("muted");
      await cfg.update("muted", next, vscode.ConfigurationTarget.Global);
      panel.setMuted(next);
      vscode.window.showInformationMessage(`Professor ${next ? "em mudo" : "ativo"}.`);
    })
  );

  panel.setMuted(vscode.workspace.getConfiguration("professor").get<boolean>("muted", false));
}

export function deactivate(): void {}
```

- [ ] **Step 4: Confirm unit tests still pass**

Run: `npm test`
Expected: PASS (todos os testes das Tasks 1-7).

- [ ] **Step 5: Compile**

Run: `npm run compile`
Expected: sem erros de tipo; gera `dist/extension.js`.

- [ ] **Step 6: Manual E2E (caminho feliz)**

Pré-requisito: `ollama serve` rodando e `ollama pull qwen3:14b` feito.
1. `F5` para abrir a janela de desenvolvimento.
2. Crie `teste.py` e digite:
   ```python
   f = open("dados.txt")
   conteudo = f.read()
   ```
3. Pare de digitar ~1,5s.
Expected: o painel 🎓 mostra uma dica ensinando sobre usar `with open(...)` (comment/why/nudge), em português.

- [ ] **Step 7: Manual E2E (degradação + mudo)**

1. Pare o Ollama (`ollama` desligado) e edite o arquivo.
   Expected: nenhum erro aparece; o painel simplesmente não muda.
2. Rode o comando "Professor: Alternar mudo" (Ctrl+Shift+P).
   Expected: painel mostra "Professor em mudo." e para de atualizar.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: wire watcher, commands, config — end-to-end MVP"
```

---

## Notas de execução

- **Pré-requisitos de máquina:** Node 18+, VSCode, Ollama com `qwen3:14b` (já instalado na 4080).
- **Fora de escopo desta fatia (vai pro plano da Fatia 2):** serviço de retrieval do StackOverflow, citação de fonte no painel, RAG vetorial.
- **Reaproveitamento:** ao implementar a Task 2/8, vale olhar o [CodingGenie](https://github.com/sebzhao/CodingGenie) (MIT) para refinar gatilhos; a Task 4 pode incorporar formulações do [GPTutor](https://github.com/GPTutor/gptutor-extension) (MIT). Nenhum dos dois é dependência de runtime.
