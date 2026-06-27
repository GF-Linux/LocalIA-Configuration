"""Juiz via Claude API (SDK oficial). Modelo: claude-opus-4-8.
NÃO passar temperature/top_p/top_k (removidos no Opus 4.8 -> 400).
A chave vem de ANTHROPIC_API_KEY (o SDK a lê sozinho); nunca hardcodar."""
import os

JUDGE_MODEL = "claude-opus-4-8"

def extract_text(resp) -> str:
    parts = []
    for block in getattr(resp, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts)

def make_claude_ask(model: str = JUDGE_MODEL):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY não definida. Exporte sua chave antes de rodar o juiz "
            "(NÃO commitar a chave)."
        )
    from anthropic import Anthropic
    client = Anthropic()  # lê ANTHROPIC_API_KEY do ambiente

    def ask(prompt: str) -> str:
        # sem temperature/top_p/top_k (Opus 4.8 rejeita). max_tokens enxuto: a saída é JSON curto.
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return extract_text(resp)

    return ask
