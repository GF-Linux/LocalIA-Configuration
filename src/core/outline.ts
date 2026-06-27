const STRUCT = /^\s*(import |from |export |def |class |function |const |public |private |let |var |type |interface |async |func )/;

export function extractOutline(text: string, maxLines = 120): string {
  const lines = text.split("\n");
  if (lines.length <= maxLines) return text;
  return lines.filter((l) => STRUCT.test(l)).join("\n");
}
