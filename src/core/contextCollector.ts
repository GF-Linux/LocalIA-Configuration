export type EditorContext = { code: string; lang: string; file: string };

export function extractContext(
  text: string,
  lang: string,
  file: string,
  cursorLine: number,
  maxLines = 30
): EditorContext {
  const lines = text.split("\n");
  const end = Math.min(cursorLine + 1, lines.length);
  const start = Math.max(0, end - maxLines);
  return { code: lines.slice(start, end).join("\n"), lang, file };
}
