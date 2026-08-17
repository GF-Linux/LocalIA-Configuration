"""Acervos de referência — pastas grandes de markdown, indexadas para busca.

O h4cker tem 460 arquivos de referência numa taxonomia por domínio. Injetar
tudo é impossível; ler do disco a cada pergunta é lento. A resposta é a mesma
das skills e da ADR 0043: índice barato, corpo sob demanda.

O índice guarda por arquivo: caminho, título, domínio (da própria árvore de
pastas) e as primeiras linhas — o suficiente para achar. O corpo só entra no
contexto quando o arquivo é escolhido, e sai com /descarregar.

O índice é DERIVADO e regenerável: nada do acervo é copiado. Mesma disciplina
do segundo-cérebro-grafo (ADR 0006/0007 do meta).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import config

DIR_INDICES = config.DIR_CONFIG / "acervos"


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


@dataclass
class Verbete:
    caminho: str          # absoluto
    titulo: str
    dominio: str          # trilha de pastas relativa, como categoria
    resumo: str           # primeiras linhas úteis
    tamanho: int
    tipo: str = "md"      # "md" | "pdf" — decide como ler o corpo

    def corpo(self, max_bytes: int = 120_000) -> str:
        if self.tipo == "pdf":
            # catálogo, não biblioteca: o corpo de um livro é o SUMÁRIO
            # (primeiras páginas), não o livro inteiro. Carregar 400 páginas
            # no contexto não é recuperação, é despejo.
            return _pdf_texto(self.caminho, ate_pagina=16)
        try:
            txt = Path(self.caminho).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"(não consegui ler: {e})"
        if len(txt) > max_bytes:
            txt = txt[:max_bytes] + f"\n\n… (cortado em {max_bytes} bytes)"
        return txt

    def tokens_aprox(self) -> int:
        if self.tipo == "pdf":
            return int(len(self.resumo) / 3.246) + 400   # sumário, não o livro
        return int(min(self.tamanho, 120_000) / 3.246)


@dataclass
class Acervo:
    nome: str
    raiz: str
    verbetes: list[Verbete] = field(default_factory=list)

    def procura(self, termo: str, limite: int = 25) -> list[Verbete]:
        t = _sem_acento(termo.strip())
        if not t:
            return self.verbetes[:limite]
        termos = t.split()

        def pontua(v: Verbete) -> int:
            alvo = _sem_acento(f"{v.titulo} {v.dominio} {v.resumo}")
            titulo = _sem_acento(v.titulo)
            p = 0
            for w in termos:
                if w in titulo:
                    p += 10
                if w in _sem_acento(v.dominio):
                    p += 4
                if w in alvo:
                    p += 1
            return p

        marcados = [(pontua(v), v) for v in self.verbetes]
        marcados = [(p, v) for p, v in marcados if p > 0]
        marcados.sort(key=lambda x: (-x[0], len(x[1].titulo)))
        return [v for _, v in marcados[:limite]]


def _titulo_e_resumo(caminho: Path) -> tuple[str, str]:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as fh:
            txt = fh.read(4000)
    except OSError:
        return caminho.stem, ""
    # tira frontmatter e imagens/badges, que não ajudam a achar
    txt = re.sub(r"^---\s*\n.*?\n---\s*\n", "", txt, flags=re.S)
    linhas = []
    for l in txt.splitlines():
        s = l.strip()
        if not s or s.startswith(("![", "[![", "<img", "<p", "</", "<div")):
            continue
        linhas.append(s.lstrip("# ").strip())
        if len(linhas) >= 6:
            break
    titulo = ""
    m = re.search(r"^#\s+(.+)", txt, re.M)
    if m:
        titulo = m.group(1).strip()
    if not titulo:
        titulo = linhas[0] if linhas else caminho.stem
    resumo = " · ".join(linhas[1:5])[:280]
    return titulo[:120], resumo


def _pdf_texto(caminho: str, ate_pagina: int = 16) -> str:
    """Texto das primeiras páginas via pdftotext. Vazio se escaneado/falhar."""
    import subprocess
    try:
        r = subprocess.run(
            ["pdftotext", "-l", str(ate_pagina), caminho, "-"],
            capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


def _pdf_titulo(caminho: str) -> str:
    """Título do metadata do PDF; cai no nome do arquivo se vazio/ruim."""
    import subprocess
    try:
        r = subprocess.run(["pdfinfo", caminho], capture_output=True,
                           text=True, timeout=20)
        for l in r.stdout.splitlines():
            if l.startswith("Title:"):
                t = l.split(":", 1)[1].strip()
                if len(t) >= 4 and not t.lower().startswith(("microsoft", "untitled")):
                    return t[:120]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return Path(caminho).stem.replace("_", " ")[:120]


def indexa(nome: str, raiz: str, com_pdf: bool = False) -> Acervo:
    base = Path(os.path.expanduser(raiz))
    verbetes = []
    if not base.is_dir():
        return Acervo(nome, str(base), verbetes)

    padroes = ["*.md"] + (["*.pdf", "*.epub"] if com_pdf else [])
    for padrao in padroes:
        for caminho in sorted(base.rglob(padrao)):
            if "/.git/" in str(caminho):
                continue
            try:
                tam = caminho.stat().st_size
            except OSError:
                continue
            rel = caminho.parent.relative_to(base)
            dominio = str(rel).replace(os.sep, " / ") if str(rel) != "." else ""
            if padrao == "*.md":
                titulo, resumo = _titulo_e_resumo(caminho)
                verbetes.append(Verbete(str(caminho), titulo, dominio,
                                        resumo, tam, "md"))
            else:
                # catálogo de livro: título + sumário como resumo pesquisável.
                # Escaneado (sem texto) entra mesmo assim, achável pelo nome.
                titulo = _pdf_titulo(str(caminho))
                sumario = _pdf_texto(str(caminho), 12)
                resumo = re.sub(r"\s+", " ", sumario)[:600] if sumario else \
                    "(sem texto extraível — provavelmente escaneado)"
                verbetes.append(Verbete(str(caminho), titulo, dominio,
                                        resumo, tam, "pdf"))
    return Acervo(nome, str(base), verbetes)


def grava(ac: Acervo) -> Path:
    DIR_INDICES.mkdir(parents=True, exist_ok=True)
    alvo = DIR_INDICES / f"{ac.nome}.json"
    dados = {
        "nome": ac.nome, "raiz": ac.raiz,
        "verbetes": [v.__dict__ for v in ac.verbetes],
    }
    alvo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return alvo


def carrega(nome: str) -> Acervo | None:
    p = DIR_INDICES / f"{nome}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return Acervo(d["nome"], d["raiz"],
                  [Verbete(**v) for v in d.get("verbetes", [])])


def lista_indices() -> list[str]:
    if not DIR_INDICES.is_dir():
        return []
    return sorted(p.stem for p in DIR_INDICES.glob("*.json"))
