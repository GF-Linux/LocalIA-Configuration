import { describe, it, expect, vi, afterEach } from "vitest";
import { askOllama } from "./ollamaClient";

const opts = { url: "http://localhost:11434", model: "qwen3:14b" };

afterEach(() => vi.restoreAllMocks());

describe("askOllama", () => {
  it("POSTa em /api/chat e devolve o content", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ message: { content: '{"skip":true}' } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const out = await askOllama([{ role: "user", content: "oi" }], opts);
    expect(out).toBe('{"skip":true}');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:11434/api/chat");
    const body = JSON.parse(init.body);
    expect(body.model).toBe("qwen3:14b");
    expect(body.stream).toBe(false);
    expect(body.format).toBe("json");
  });

  it("lança em HTTP não-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(askOllama([], opts)).rejects.toThrow(/500/);
  });
});
