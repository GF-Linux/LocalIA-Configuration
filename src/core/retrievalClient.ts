import type { RetrievalResult } from "./types";

export async function fetchRetrieval(
  query: string,
  opts: { url: string; k: number; signal?: AbortSignal; timeoutMs?: number }
): Promise<RetrievalResult[]> {
  const timeoutMs = opts.timeoutMs ?? 5000;
  const signal = opts.signal
    ? AbortSignal.any([opts.signal, AbortSignal.timeout(timeoutMs)])
    : AbortSignal.timeout(timeoutMs);
  const url = `${opts.url}/retrieve?q=${encodeURIComponent(query)}&k=${opts.k}`;
  try {
    const res = await fetch(url, { signal });
    if (!res.ok) return [];
    const data: unknown = await res.json();
    return Array.isArray(data) ? (data as RetrievalResult[]) : [];
  } catch {
    return [];
  }
}
