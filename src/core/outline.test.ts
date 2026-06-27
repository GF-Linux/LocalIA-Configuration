import { describe, it, expect } from "vitest";
import { extractOutline } from "./outline";

describe("extractOutline", () => {
  it("arquivo pequeno: devolve tudo", () => {
    const text = "import os\n\ndef a():\n    return 1";
    expect(extractOutline(text, 120)).toBe(text);
  });
  it("arquivo grande: só linhas estruturais", () => {
    const body = Array.from({ length: 200 }, (_, i) => `    x = ${i}`).join("\n");
    const text = `import os\nclass Foo:\n${body}\ndef bar():\n${body}`;
    const out = extractOutline(text, 120);
    expect(out).toContain("import os");
    expect(out).toContain("class Foo:");
    expect(out).toContain("def bar():");
    expect(out).not.toContain("x = 150");
  });
});
