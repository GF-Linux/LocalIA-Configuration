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
