import { describe, it, expect } from "vitest";
import { buildTutorMessages } from "./promptBuilder";

describe("buildTutorMessages", () => {
  const msgs = buildTutorMessages({ code: "open('f')", lang: "python", file: "f.py" });

  it("tem system + user", () => {
    expect(msgs.map((m) => m.role)).toEqual(["system", "user"]);
  });

  it("system instrui ensino (não resolver) e JSON em português", () => {
    const s = msgs[0].content.toLowerCase();
    expect(s).toContain("professor");
    expect(s).toContain("json");
    expect(s).toContain("portugu");
    expect(s).toContain("skip");
  });

  it("user inclui o código e a linguagem", () => {
    expect(msgs[1].content).toContain("open('f')");
    expect(msgs[1].content).toContain("python");
  });
});
