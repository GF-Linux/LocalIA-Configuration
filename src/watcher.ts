import * as vscode from "vscode";
import { TriggerState, initialTriggerState, decideTrigger, hashCode } from "./core/triggerPolicy";
import { extractContext } from "./core/contextCollector";
import { askOllama } from "./core/ollamaClient";
import { parseHint } from "./core/responseParser";
import { ProfessorViewProvider } from "./panel";
import { buildQueryMessages, cleanQuery, heuristicQuery } from "./core/queryExtractor";
import { fetchRetrieval } from "./core/retrievalClient";
import { buildGroundedTutorMessages } from "./core/groundedPromptBuilder";
import { extractOutline } from "./core/outline";
import { buildPanoramaMessages, parsePanorama } from "./core/panorama";
import { getIntent } from "./intentStore";

export class Watcher {
  private state: TriggerState = initialTriggerState();
  private timer: ReturnType<typeof setTimeout> | undefined;
  private abort: AbortController | undefined;
  private lastPanoramaMs = -Infinity;

  constructor(
    private readonly panel: ProfessorViewProvider,
    private readonly context: vscode.ExtensionContext
  ) {}

  private cfg() {
    return vscode.workspace.getConfiguration("professor");
  }

  /** Chamado em edição/salvar; agenda uma análise com debounce. */
  schedule(): void {
    const cfg = this.cfg(); // Fix 5: read cfg once, reuse for both checks
    if (cfg.get<boolean>("muted")) return;
    if (this.timer) clearTimeout(this.timer);
    const debounce = cfg.get<number>("debounceMs", 1500);
    this.timer = setTimeout(() => void this.analyzeNow(), debounce);
  }

  /** Análise imediata (comando "comentar agora" ou fim do debounce).
   *  force=true: bypass mute + decideTrigger (explicit user command).
   *  force=false: respect mute and cooldown/dedup gate (auto path). */
  async analyzeNow(force = false): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    const cfg = this.cfg();

    // Fix 1: mute check only on auto path; forced command always runs
    if (!force && cfg.get<boolean>("muted")) return;

    // cursorLine is 0-based (matches extractContext's internal cursorLine + 1 slice).
    // Do NOT add +1 here — extractContext already adds 1 before slicing.
    const ctx = extractContext(
      editor.document.getText(),
      editor.document.languageId,
      editor.document.fileName,
      editor.selection.active.line,
      cfg.get<number>("maxContextLines", 30)
    );
    if (!ctx.code.trim()) return;

    if (!force) {
      // Fix 1: respect decideTrigger cooldown/dedup gate on auto path
      const decision = decideTrigger(
        this.state,
        Date.now(),
        hashCode(ctx.code),
        cfg.get<number>("cooldownSeconds", 20) * 1000
      );
      if (!decision.fire) return;
      this.state = decision.nextState;
    } else {
      // Fix 1: forced path — skip gate but reset cooldown window so next auto-trigger
      // gets a fresh cooldown from this forced run
      this.state = { lastFiredMs: Date.now(), lastHash: hashCode(ctx.code) };
    }

    // Fix 7: don't spend GPU when panel is closed; forced command always proceeds
    if (!force && !this.panel.isVisible()) return;

    this.abort?.abort();
    this.abort = new AbortController();
    const signal = this.abort.signal;
    try {
      const intent = getIntent(this.context);

      // 1) query de busca (modelo pequeno, fail-quiet → heurística)
      let query = "";
      try {
        const rawQuery = await askOllama(buildQueryMessages(ctx), {
          url: cfg.get<string>("ollamaUrl", "http://localhost:11434"),
          model: cfg.get<string>("queryModel", "qwen2.5-coder:1.5b"),
          timeoutMs: 20000,
          signal,
        });
        query = cleanQuery(rawQuery);
      } catch { /* cai no fallback abaixo */ }
      if (!query) query = heuristicQuery(ctx.code, ctx.lang);

      // 2) busca no StackOverflow (fail-quiet → [])
      const sources = await fetchRetrieval(query, {
        url: cfg.get<string>("retrievalUrl", "http://localhost:8765"),
        k: 3,
        signal,
      });

      // 3) ensino fundamentado
      const raw = await askOllama(buildGroundedTutorMessages(ctx, sources, intent), {
        url: cfg.get<string>("ollamaUrl", "http://localhost:11434"),
        model: cfg.get<string>("model", "qwen3:14b"),
        timeoutMs: cfg.get<number>("timeoutSeconds", 120) * 1000,
        signal,
      });
      this.panel.update(parseHint(raw), force);
    } catch (e) {
      // Fail-quiet para o auto path; mas um comando explícito do usuário merece feedback
      // de erro (senão "Comentar agora" parece não fazer nada). AbortError de uma chamada
      // substituída é normal — não reporta.
      if (force && !(e instanceof Error && e.name === "AbortError")) {
        vscode.window.showWarningMessage(`Professor: não consegui gerar a dica — ${String(e)}`);
      }
    }
  }

  /** Gera o panorama do arquivo ativo (estrutura + próximo passo). Tem cooldown próprio.
   *  force=true: bypass cooldown (comando explícito). */
  async panoramaNow(force = false): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) return;
    const cfg = this.cfg();
    const cd = cfg.get<number>("panoramaCooldownSeconds", 60) * 1000;
    if (!force && Date.now() - this.lastPanoramaMs < cd) return;
    if (!force && !this.panel.isVisible()) return;
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

  dispose(): void {
    if (this.timer) clearTimeout(this.timer);
    this.abort?.abort();
  }
}
