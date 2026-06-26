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
