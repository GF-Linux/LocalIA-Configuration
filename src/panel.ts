import * as vscode from "vscode";
import { renderHintHtml, renderPanoramaHtml } from "./core/renderHint";
import type { Hint } from "./core/responseParser";
import type { Panorama } from "./core/panorama";

export class ProfessorViewProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "professor.view";
  private view?: vscode.WebviewView;
  private muted = false;
  private lastHintForRender: Hint | null = null;
  private panorama: Panorama | null = null;

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

  update(hint: Hint | null, force = false): void {
    if (!force && this.muted) return;
    this.lastHintForRender = hint;
    this.render(hint);
  }

  updatePanorama(panorama: Panorama | null): void {
    this.panorama = panorama;
    this.render(this.lastHintForRender);
  }

  // Fix 7: expose visibility so watcher can skip GPU work when panel is hidden
  isVisible(): boolean {
    return this.view?.visible ?? false;
  }

  private render(hint: Hint | null): void {
    if (!this.view) return;
    const cssUri = this.view.webview.asWebviewUri(
      vscode.Uri.joinPath(this.extensionUri, "media", "panel.css")
    );
    // Fix 2: charset + CSP for a no-script webview that loads only its own stylesheet
    const csp = this.view.webview.cspSource;
    const body = `${renderHintHtml(hint, this.muted)}${renderPanoramaHtml(this.panorama)}`;
    this.view.webview.html = `<!DOCTYPE html><html><head>
      <meta charset="utf-8">
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${csp};">
      <link rel="stylesheet" href="${cssUri}"></head>
      <body>${body}</body></html>`;
  }
}
