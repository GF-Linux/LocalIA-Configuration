import { describe, it, expect } from "vitest";
import { extractContext } from "./contextCollector";

const text = ["a=1", "b=2", "c=3", "d=4", "e=5"].join("\n");

describe("extractContext", () => {
  it("pega as últimas N linhas até o cursor", () => {
    const ctx = extractContext(text, "python", "f.py", 4, 3);
    expect(ctx.code).toBe("c=3\nd=4\ne=5");
    expect(ctx.lang).toBe("python");
    expect(ctx.file).toBe("f.py");
  });

  it("não estoura no começo do arquivo", () => {
    expect(extractContext(text, "python", "f.py", 1, 10).code).toBe("a=1\nb=2");
  });

  it("trata linha de cursor além do fim", () => {
    expect(extractContext(text, "python", "f.py", 99, 2).code).toBe("d=4\ne=5");
  });
});
