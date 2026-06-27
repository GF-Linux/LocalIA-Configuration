import type { ChatMessage } from "./promptBuilder";
import { intentClause, type Intent } from "./intent";

export type Panorama = { structure: string; next: string };

const BASE = `Você é um professor de programação, em português do Brasil. Olhe o ESQUELETO do
arquivo do aluno e dê uma visão de PANORAMA: a estrutura/organização e o próximo passo.
Regras:
- "structure": uma observação curta sobre organização/arquitetura (ou o que falta).
- "next": o próximo passo concreto / para onde isso vai.
- Se o arquivo é trivial demais para um panorama, responda exatamente {"skip": true}.
Responda SOMENTE em JSON válido: {"structure":"...","next":"..."}  ou  {"skip": true}`;

export function buildPanoramaMessages(
  outline: string,
  lang: string,
  intent: Intent | undefined
): ChatMessage[] {
  const clause = intentClause(intent);
  const system = clause ? `${BASE}\n${clause}` : BASE;
  return [
    { role: "system", content: system },
    { role: "user", content: `Linguagem: ${lang}\nEsqueleto do arquivo:\n${outline}` },
  ];
}

export function parsePanorama(raw: string): Panorama | null {
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
  if (obj && typeof obj.structure === "string" && typeof obj.next === "string") {
    return { structure: obj.structure, next: obj.next };
  }
  return null;
}
