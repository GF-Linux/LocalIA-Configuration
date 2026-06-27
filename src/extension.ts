import * as vscode from "vscode";
import { ProfessorViewProvider } from "./panel";
import { Watcher } from "./watcher";
import { getIntent } from "./intentStore";

export function activate(context: vscode.ExtensionContext): void {
  const panel = new ProfessorViewProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(ProfessorViewProvider.viewType, panel)
  );

  const watcher = new Watcher(panel, context);
  context.subscriptions.push(watcher);

  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document === vscode.window.activeTextEditor?.document) watcher.schedule();
    }),
    // Fix 4: guard save handler to active document only (matches onDidChangeTextDocument)
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (doc === vscode.window.activeTextEditor?.document) {
        watcher.schedule();
        void watcher.panoramaNow();
      }
    }),
    // Fix 1: pass force=true so "comentar agora" bypasses cooldown/dedup and mute
    vscode.commands.registerCommand("professor.commentNow", () => void watcher.analyzeNow(true)),
    vscode.commands.registerCommand("professor.toggleMute", async () => {
      const cfg = vscode.workspace.getConfiguration("professor");
      const next = !cfg.get<boolean>("muted");
      await cfg.update("muted", next, vscode.ConfigurationTarget.Global);
      panel.setMuted(next);
      vscode.window.showInformationMessage(`Professor ${next ? "em mudo" : "ativo"}.`);
    }),
    vscode.commands.registerCommand("professor.panorama", () => void watcher.panoramaNow(true)),
    vscode.commands.registerCommand("professor.setIntent", async () => {
      const { promptIntent } = await import("./intentStore");
      await promptIntent(context);
    }),
    // Fix 3: sync mute state when changed via Settings UI (not via command)
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("professor.muted")) {
        panel.setMuted(
          vscode.workspace.getConfiguration("professor").get<boolean>("muted", false)
        );
      }
    })
  );

  panel.setMuted(vscode.workspace.getConfiguration("professor").get<boolean>("muted", false));

  // Offer intent prompt once on activation if not yet set (non-blocking)
  if (getIntent(context) === undefined) {
    void (async () => {
      const { promptIntent } = await import("./intentStore");
      await promptIntent(context);
    })();
  }
}

export function deactivate(): void {}
