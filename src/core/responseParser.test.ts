import { describe, it, expect } from "vitest";
import { parseHint } from "./responseParser";

describe("parseHint", () => {
  it("parseia uma dica completa", () => {
    const h = parseHint('{"comment":"c","why":"w","nudge":"n"}');
    expect(h).toEqual({ comment: "c", why: "w", nudge: "n" });
  });

  it("aceita JSON cercado de texto/sujeira", () => {
    expect(parseHint('lixo {"comment":"c","why":"w","nudge":"n"} fim'))
      .toEqual({ comment: "c", why: "w", nudge: "n" });
  });

  it("retorna null em skip", () => {
    expect(parseHint('{"skip": true}')).toBeNull();
  });

  it("retorna null em JSON inválido", () => {
    expect(parseHint("não é json")).toBeNull();
  });

  it("retorna null se faltar campo", () => {
    expect(parseHint('{"comment":"c"}')).toBeNull();
  });
});
