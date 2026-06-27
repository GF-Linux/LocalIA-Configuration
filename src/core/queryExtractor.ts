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
