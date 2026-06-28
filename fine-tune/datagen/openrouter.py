"""Cliente GLM 5.2 via OpenRouter (OpenAI-compat). Chave via OPENROUTER_API_KEY.
A lógica de corpo/parse é pura; o transporte (urllib) é injetável para testes."""
import json
import os
import time
import urllib.request
import urllib.error

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GLM_MODEL = "z-ai/glm-5.2"


def build_body(model: str, messages: list, *, max_tokens: int = 512,
               reasoning_enabled: bool = False) -> dict:
    # GLM 5.2 raciocina por padrão: a saída fica ~5x maior e ~3x mais lenta
    # (medido no piloto: 14.5s vs 4.2s/call). Para dica/panorama (JSON curto) não
    # precisamos de reasoning; desligamos e limitamos max_tokens p/ acelerar e baratear.
    return {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        "reasoning": {"enabled": reasoning_enabled},
    }


def parse_completion(resp_json: dict):
    content = resp_json["choices"][0]["message"]["content"]
    usage = resp_json.get("usage") or {}
    return content, {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


def _urllib_transport(url: str, body: dict, key: str):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read())


def _is_retryable(status: int) -> bool:
    return status == 429 or 500 <= status < 600


def make_glm_ask(model: str = GLM_MODEL, *, url: str = OPENROUTER_URL,
                 on_usage=None, transport=None, retries: int = 4,
                 backoff: float = 2.0, sleep=time.sleep,
                 max_tokens: int = 512, reasoning_enabled: bool = False):
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY não definida. Exporte sua chave do OpenRouter antes de "
            "gerar dados (NÃO commitar a chave)."
        )
    if transport is None:
        def transport(u, b):
            return _urllib_transport(u, b, key)

    def ask(messages: list) -> str:
        body = build_body(model, messages, max_tokens=max_tokens,
                          reasoning_enabled=reasoning_enabled)
        last = None
        for attempt in range(retries):
            err = None
            try:
                status, resp = transport(url, body)
            except urllib.error.HTTPError as e:
                status, resp, err = e.code, None, e
            if resp is not None and status == 200:
                content, usage = parse_completion(resp)
                if on_usage:
                    on_usage(usage)
                return content
            # Preserve the original HTTPError (with its body/reason) when present;
            # only fall back to a blander RuntimeError for status-only failures.
            last = err or RuntimeError(f"status {status}")
            if _is_retryable(status):
                sleep(backoff * (2 ** attempt))
                continue
            detail = getattr(last, "reason", None) or resp
            raise RuntimeError(f"OpenRouter status {status}: {detail}")
        raise RuntimeError(f"OpenRouter falhou após {retries} tentativas: {last}")

    return ask
