import { describe, it, expect } from "vitest";
import { buildQueryMessages, cleanQuery, heuristicQuery } from "./queryExtractor";

describe("buildQueryMessages", () => {
  const msgs = buildQueryMessages({ code: "f = open('x')", lang: "python", file: "a.py" });
  it("system pede query curta em inglês, só palavras-chave", () => {
    const s = msgs[0].content.toLowerCase();
    expect(s).toContain("english");
    expect(s).toContain("search");
  });
  it("user inclui o código", () => {
    expect(msgs[1].content).toContain("f = open('x')");
  });
});

describe("cleanQuery", () => {
  it("tira aspas e limita palavras", () => {
    expect(cleanQuery('"python read file with open"')).toBe("python read file with open");
  });
  it("pega só a primeira linha", () => {
    expect(cleanQuery("python open file\nextra junk")).toBe("python open file");
  });
  it("limita a 12 palavras", () => {
    const q = cleanQuery("a b c d e f g h i j k l m n o");
    expect(q.split(" ").length).toBe(12);
  });
});

describe("heuristicQuery", () => {
  it("extrai identificadores + linguagem", () => {
    const q = heuristicQuery("conteudo = open('dados.txt').read()", "python");
    expect(q).toContain("python");
    expect(q.toLowerCase()).toContain("open");
  });
  it("não estoura com código vazio", () => {
    expect(heuristicQuery("", "python")).toBe("python");
  });
});
