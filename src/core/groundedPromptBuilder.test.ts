import { describe, it, expect } from "vitest";
import { buildGroundedTutorMessages } from "./groundedPromptBuilder";
import { intentClause } from "./intent";

const ctx = { code: "open('f')", lang: "python", file: "f.py" };
const sources = [{ title: "Reading files", url: "questions/123", snippet: "use with open()" }];

describe("intentClause", () => {
  it("calibra por intenção", () => {
    expect(intentClause("treino").toLowerCase()).toContain("fundament");
    expect(intentClause("projeto").toLowerCase()).toContain("estrutura");
    expect(intentClause(undefined)).toBe("");
  });
});

describe("buildGroundedTutorMessages", () => {
  it("system pede JSON com source e ensino em PT", () => {
    const s = buildGroundedTutorMessages(ctx, sources, "treino")[0].content.toLowerCase();
    expect(s).toContain("json");
    expect(s).toContain("source");
    expect(s).toContain("portugu");
  });
  it("user inclui os trechos do StackOverflow quando há fontes", () => {
    const u = buildGroundedTutorMessages(ctx, sources, undefined)[1].content;
    expect(u).toContain("use with open()");
    expect(u).toContain("Reading files");
    expect(u).toContain("open('f')");
  });
  it("sem fontes: não inventa seção de fontes, ainda ensina", () => {
    const u = buildGroundedTutorMessages(ctx, [], undefined)[1].content;
    expect(u).toContain("open('f')");
    expect(u.toLowerCase()).not.toContain("stackoverflow:");
  });
});
