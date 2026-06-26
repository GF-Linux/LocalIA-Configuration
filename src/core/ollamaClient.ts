import type { ChatMessage } from "./promptBuilder";

export async function askOllama(
  messages: ChatMessage[],
  opts: { url: string; model: string; signal?: AbortSignal; timeoutMs?: number }
): Promise<string> {
  // Fix 6: combine caller signal with a timeout so a hung Ollama self-recovers.
  // Node 24 supports AbortSignal.any() and AbortSignal.timeout().
  // Default 120s: a 14B model cold-starts (loading into VRAM) can take ~50s.
  const timeoutMs = opts.timeoutMs ?? 120000;
  const signal = opts.signal
    ? AbortSignal.any([opts.signal, AbortSignal.timeout(timeoutMs)])
    : AbortSignal.timeout(timeoutMs);

  const res = await fetch(`${opts.url}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: opts.model,
      messages,
      stream: false,
      format: "json",
    }),
    signal,
  });
  if (!res.ok) throw new Error(`Ollama HTTP ${res.status}`);
  const data: any = await res.json();
  return data?.message?.content ?? "";
}
