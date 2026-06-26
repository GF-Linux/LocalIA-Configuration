import { describe, it, expect } from "vitest";
import { initialTriggerState, decideTrigger, hashCode } from "./triggerPolicy";

describe("decideTrigger", () => {
  it("dispara na primeira vez", () => {
    const r = decideTrigger(initialTriggerState(), 1000, "h1", 5000);
    expect(r.fire).toBe(true);
    expect(r.nextState).toEqual({ lastFiredMs: 1000, lastHash: "h1" });
  });

  it("NÃO dispara dentro do cooldown", () => {
    const s = { lastFiredMs: 1000, lastHash: "h1" };
    expect(decideTrigger(s, 3000, "h2", 5000).fire).toBe(false);
  });

  it("NÃO dispara se o hash do código não mudou (dedup)", () => {
    const s = { lastFiredMs: 1000, lastHash: "h1" };
    expect(decideTrigger(s, 9000, "h1", 5000).fire).toBe(false);
  });

  it("dispara após cooldown se o código mudou", () => {
    const s = { lastFiredMs: 1000, lastHash: "h1" };
    const r = decideTrigger(s, 9000, "h2", 5000);
    expect(r.fire).toBe(true);
    expect(r.nextState).toEqual({ lastFiredMs: 9000, lastHash: "h2" });
  });

  it("hashCode é estável e distingue strings", () => {
    expect(hashCode("abc")).toBe(hashCode("abc"));
    expect(hashCode("abc")).not.toBe(hashCode("abd"));
  });
});
