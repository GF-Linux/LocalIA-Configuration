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
