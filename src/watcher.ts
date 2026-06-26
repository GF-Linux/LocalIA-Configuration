import * as vscode from "vscode";
import { TriggerState, initialTriggerState, decideTrigger, hashCode } from "./core/triggerPolicy";
import { extractContext } from "./core/contextCollector";
import { buildTutorMessages } from "./core/promptBuilder";
import { askOllama } from "./core/ollamaClient";
import { parseHint } from "./core/responseParser";
import { ProfessorViewProvider } from "./panel";

export class Watcher {
  private state: TriggerState = initialTriggerState();
  private timer: ReturnType<typeof setTimeout> | undefined;
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
