import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchRetrieval } from "./retrievalClient";

const opts = { url: "http://localhost:8765", k: 3 };
afterEach(() => vi.restoreAllMocks());

describe("fetchRetrieval", () => {
  it("GET /retrieve com q e k, devolve a lista", async () => {
    const data = [{ title: "T", url: "U", snippet: "S" }];
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
    vi.stubGlobal("fetch", fetchMock);
    const out = await fetchRetrieval("python open", opts);
    expect(out).toEqual(data);
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("/retrieve?");
    expect(url).toContain("q=python%20open");
    expect(url).toContain("k=3");
  });
  it("HTTP não-ok → []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    expect(await fetchRetrieval("x", opts)).toEqual([]);
  });
  it("erro de rede → []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("down")));
    expect(await fetchRetrieval("x", opts)).toEqual([]);
  });
  it("JSON não-lista → []", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }));
    expect(await fetchRetrieval("x", opts)).toEqual([]);
  });
});
