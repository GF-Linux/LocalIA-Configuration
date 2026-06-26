import { describe, it, expect } from "vitest";
import { EXT_VERSION } from "./version";

describe("version", () => {
  it("expõe uma string semver", () => {
    expect(EXT_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });
});
