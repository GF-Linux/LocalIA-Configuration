import * as vscode from "vscode";
import { EXT_VERSION } from "./core/version";

export function activate(_context: vscode.ExtensionContext): void {
  console.log(`Professor ${EXT_VERSION} ativo`);
}

export function deactivate(): void {}
