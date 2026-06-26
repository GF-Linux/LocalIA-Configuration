export type Hint = { comment: string; why: string; nudge: string };

export function parseHint(raw: string): Hint | null {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start === -1 || end <= start) return null;
  let obj: any;
  try {
    obj = JSON.parse(raw.slice(start, end + 1));
  } catch {
    return null;
  }
  if (obj && obj.skip === true) return null;
  const ok =
    obj &&
    typeof obj.comment === "string" &&
    typeof obj.why === "string" &&
    typeof obj.nudge === "string";
  return ok ? { comment: obj.comment, why: obj.why, nudge: obj.nudge } : null;
}
