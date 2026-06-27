import { describe, it, expect } from "vitest";
import { buildPanoramaMessages, parsePanorama } from "./panorama";

describe("buildPanoramaMessages", () => {
  const msgs = buildPanoramaMessages("class Foo:\ndef bar():", "python", "projeto");
  it("system pede structure e next em JSON, PT", () => {
    const s = msgs[0].content.toLowerCase();
    expect(s).toContain("structure");
    expect(s).toContain("next");
    expect(s).toContain("portugu");
  });
  it("user inclui o outline", () => {
    expect(msgs[1].content).toContain("class Foo:");
  });
});

describe("parsePanorama", () => {
  it("parseia panorama completo", () => {
    expect(parsePanorama('{"structure":"s","next":"n"}')).toEqual({ structure: "s", next: "n" });
  });
  it("skip → null", () => {
    expect(parsePanorama('{"skip": true}')).toBeNull();
  });
  it("JSON inválido → null", () => {
    expect(parsePanorama("nope")).toBeNull();
  });
  it("campo faltando → null", () => {
    expect(parsePanorama('{"structure":"s"}')).toBeNull();
  });
});
