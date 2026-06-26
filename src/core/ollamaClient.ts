import type { ChatMessage } from "./promptBuilder";

export async function askOllama(
  messages: ChatMessage[],
  opts: { url: string; model: string; signal?: AbortSignal }
): Promise<string> {
  const res = await fetch(`${opts.url}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: opts.model,
      messages,
      stream: false,
      format: "json",
    }),
    signal: opts.signal,
  });
  if (!res.ok) throw new Error(`Ollama HTTP ${res.status}`);
  const data: any = await res.json();
  return data?.message?.content ?? "";
}
