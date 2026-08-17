"""Provedores de modelo, com fluxo por streaming.

Duas implementacoes atras da mesma interface: Ollama (local) e qualquer API
compativel com OpenAI. A abstracao existe para que trocar de modelo — inclusive
de FAMILIA de modelo — seja uma linha de TOML.

Streaming nao e enfeite: a 12 tok/s, esperar a resposta inteira antes de
mostrar qualquer coisa e a diferenca entre util e insuportavel.

So biblioteca padrao: a maquina nao tem pip.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Iterator

HOST_OLLAMA = "http://127.0.0.1:11434"


@dataclass
class Pedaco:
    """Um evento do fluxo."""
    texto: str = ""            # conteudo visivel
    pensamento: str = ""       # raciocinio, quando o modelo separa
    fim: bool = False
    chamadas: list = field(default_factory=list)   # tool calls acumuladas
    erro: str = ""
    # metricas, so no pedaco final
    tok_prompt: int = 0
    tok_saida: int = 0
    segundos: float = 0.0


class ErroProvedor(Exception):
    pass


def _post_stream(url: str, corpo: dict, cabecalhos: dict,
                 timeout: int = 3600) -> Iterator[dict]:
    """POST que devolve um dicionario por linha do fluxo."""
    req = urllib.request.Request(
        url, data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json", **cabecalhos})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:400]
        raise ErroProvedor(f"HTTP {e.code}: {detalhe}") from None
    except urllib.error.URLError as e:
        raise ErroProvedor(f"nao consegui falar com {url}: {e.reason}") from None
    with resp:
        for linha in resp:
            linha = linha.decode("utf-8", "replace").strip()
            if not linha:
                continue
            if linha.startswith("data: "):          # SSE (openai-compat)
                linha = linha[6:].strip()
                if linha == "[DONE]":
                    return
            try:
                yield json.loads(linha)
            except json.JSONDecodeError:
                continue


class Provedor:
    def __init__(self, mod):
        self.mod = mod

    def conversa(self, mensagens: list[dict], ferramentas: list | None,
                 think: bool) -> Iterator[Pedaco]:
        raise NotImplementedError

    def disponivel(self) -> tuple[bool, str]:
        raise NotImplementedError


# ----------------------------------------------------------------- ollama --

class Ollama(Provedor):
    def disponivel(self) -> tuple[bool, str]:
        try:
            with urllib.request.urlopen(f"{HOST_OLLAMA}/api/tags", timeout=5) as r:
                dados = json.load(r)
        except Exception:
            return False, ("servidor do Ollama nao responde. Suba com:\n"
                           "    ~/.local/ollama-dist/bin/ollama serve &")
        nomes = {m["name"] for m in dados.get("models", [])}
        if self.mod.modelo not in nomes:
            return False, (f"o modelo {self.mod.modelo!r} nao esta baixado.\n"
                           f"    ollama pull {self.mod.modelo}")
        return True, ""

    def conversa(self, mensagens, ferramentas, think):
        corpo = {
            "model": self.mod.modelo,
            "messages": mensagens,
            "stream": True,
            "think": think,
            "keep_alive": "30m",
            "options": {
                "num_ctx": self.mod.n_ctx,
                "temperature": self.mod.temperatura,
            },
        }
        if ferramentas:
            corpo["tools"] = ferramentas
        chamadas: list = []
        try:
            for d in _post_stream(f"{HOST_OLLAMA}/api/chat", corpo, {}):
                msg = d.get("message") or {}
                if msg.get("tool_calls"):
                    chamadas.extend(msg["tool_calls"])
                if msg.get("thinking"):
                    yield Pedaco(pensamento=msg["thinking"])
                if msg.get("content"):
                    yield Pedaco(texto=msg["content"])
                if d.get("done"):
                    yield Pedaco(
                        fim=True, chamadas=chamadas,
                        tok_prompt=d.get("prompt_eval_count") or 0,
                        tok_saida=d.get("eval_count") or 0,
                        segundos=(d.get("total_duration") or 0) / 1e9,
                    )
                    return
        except ErroProvedor as e:
            yield Pedaco(fim=True, erro=str(e))
            return
        yield Pedaco(fim=True, chamadas=chamadas)


# --------------------------------------------------------- openai-compat --

class OpenAICompat(Provedor):
    def disponivel(self) -> tuple[bool, str]:
        ok, motivo = self.mod.pronto
        return (True, "") if ok else (False, motivo)

    def conversa(self, mensagens, ferramentas, think):
        corpo = {
            "model": self.mod.modelo,
            "messages": mensagens,
            "stream": True,
            "temperature": self.mod.temperatura,
        }
        if ferramentas:
            corpo["tools"] = ferramentas
        if self.mod.esforco:
            corpo["reasoning_effort"] = self.mod.esforco
        cab = {"Authorization": f"Bearer {self.mod.chave}"}
        # as chamadas de ferramenta chegam em fatias e precisam ser costuradas
        parciais: dict[int, dict] = {}
        try:
            for d in _post_stream(f"{self.mod.base_url}/chat/completions",
                                  corpo, cab):
                escolhas = d.get("choices") or []
                if not escolhas:
                    continue
                delta = escolhas[0].get("delta") or {}
                if delta.get("reasoning_content"):
                    yield Pedaco(pensamento=delta["reasoning_content"])
                if delta.get("content"):
                    yield Pedaco(texto=delta["content"])
                for tc in delta.get("tool_calls") or []:
                    i = tc.get("index", 0)
                    alvo = parciais.setdefault(
                        i, {"function": {"name": "", "arguments": ""}})
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        alvo["function"]["name"] = fn["name"]
                    if fn.get("arguments"):
                        alvo["function"]["arguments"] += fn["arguments"]
                if escolhas[0].get("finish_reason"):
                    yield Pedaco(fim=True,
                                 chamadas=[parciais[k] for k in sorted(parciais)])
                    return
        except ErroProvedor as e:
            yield Pedaco(fim=True, erro=str(e))
            return
        yield Pedaco(fim=True, chamadas=[parciais[k] for k in sorted(parciais)])


def cria(mod) -> Provedor:
    if mod.provedor == "ollama":
        return Ollama(mod)
    if mod.provedor == "openai-compat":
        return OpenAICompat(mod)
    raise ErroProvedor(f"provedor desconhecido: {mod.provedor!r}")
