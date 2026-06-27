export type Hint = {
  comment: string;
  why: string;
  nudge: string;
  /** Optional idiomatic code snippet illustrating the fix. */
  suggestion?: string;
  source?: { title: string; url: string };
};

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
  if (!ok) return null;
  const hint: Hint = { comment: obj.comment, why: obj.why, nudge: obj.nudge };
  if (typeof obj.suggestion === "string" && obj.suggestion.trim()) {
    hint.suggestion = obj.suggestion;
  }
  const s = obj.source;
  if (s && typeof s.title === "string" && typeof s.url === "string") {
    hint.source = { title: s.title, url: s.url };
  }
  return hint;
}
