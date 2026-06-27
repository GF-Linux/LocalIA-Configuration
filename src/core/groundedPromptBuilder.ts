import type { EditorContext } from "./contextCollector";
import type { ChatMessage } from "./promptBuilder";
import type { RetrievalResult } from "./types";
import { intentClause, type Intent } from "./intent";

const BASE = `Você é um professor de programação que ensina na prática, em português do Brasil.
Ensine UM ponto de aprendizado relevante, fundamentado nos trechos do StackOverflow quando houver.
Regras:
- Ensine o PORQUÊ e o idioma correto; NÃO reescreva todo o código (dê um empurrão).
- Em "suggestion", um trecho CURTO de código idiomático (só as linhas relevantes).
- Em "source", repita {title,url} da fonte do StackOverflow que você usou (omita se não usou nenhuma).
- Se não houver nada que valha a pena ensinar, responda exatamente {"skip": true}.
Responda SOMENTE em JSON válido:
{"comment":"...","why":"...","nudge":"...","suggestion":"...","source":{"title":"...","url":"..."}}  ou  {"skip": true}`;

export function buildGroundedTutorMessages(
  ctx: EditorContext,
  sources: RetrievalResult[],
  intent: Intent | undefined
): ChatMessage[] {
  const clause = intentClause(intent);
  const system = clause ? `${BASE}\n${clause}` : BASE;
  let user = `Linguagem: ${ctx.lang}\nArquivo: ${ctx.file}\nCódigo recente:\n\`\`\`${ctx.lang}\n${ctx.code}\n\`\`\``;
  if (sources.length > 0) {
    const blocks = sources
      .map((s) => `- ${s.title} (${s.url})\n  ${s.snippet}`)
      .join("\n");
    user += `\n\nTrechos do StackOverflow:\n${blocks}`;
  }
  return [
    { role: "system", content: system },
    { role: "user", content: user },
  ];
}
