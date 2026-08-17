"""Skills e contexto de projeto.

Sao 176 skills nesta maquina. Injetar todas seria centenas de milhares de
tokens — impossivel num contexto de 16k, e caro num de 131k.

O desenho e o mesmo da ADR 0043 do autor: RECUPERACAO, nao prompt. O indice
carrega so `name` + `description` (uma linha por skill, ~4k tokens no total, e
nem isso vai para o modelo); o CORPO entra so quando a skill e escolhida, e
some quando descarregada.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

DIR_SKILLS = Path.home() / ".claude" / "skills"


@dataclass
class Skill:
    nome: str
    descricao: str
    caminho: Path

    def corpo(self) -> str:
        try:
            txt = self.caminho.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return f"(nao consegui ler a skill: {e})"
        # tira o frontmatter: ja esta resumido no indice
        m = re.match(r"\s*---\s*\n.*?\n---\s*\n(.*)", txt, re.S)
        return (m.group(1) if m else txt).strip()

    def tokens_aprox(self) -> int:
        # 3,246 chars/token, medido no tokenizador do proprio qwen3.8
        return int(len(self.corpo()) / 3.246)


def _frontmatter(txt: str) -> dict:
    m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n", txt, re.S)
    if not m:
        return {}
    out = {}
    for linha in m.group(1).splitlines():
        if ":" in linha and not linha.startswith((" ", "\t", "-", "#")):
            k, v = linha.split(":", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def indice() -> dict[str, Skill]:
    """Todas as skills achadas, por nome. Le so o cabecalho de cada arquivo."""
    achadas: dict[str, Skill] = {}
    if not DIR_SKILLS.is_dir():
        return achadas
    for caminho in sorted(DIR_SKILLS.rglob("SKILL.md")):
        try:
            with open(caminho, encoding="utf-8", errors="replace") as fh:
                cabeca = fh.read(4000)
        except OSError:
            continue
        fm = _frontmatter(cabeca)
        nome = fm.get("name") or caminho.parent.name
        if nome in achadas:                     # primeira ganha; evita colisao
            continue
        achadas[nome] = Skill(
            nome=nome,
            descricao=fm.get("description", "").strip(),
            caminho=caminho,
        )
    return achadas


def procura(idx: dict[str, Skill], termo: str) -> list[Skill]:
    """Busca simples por nome e descricao, sem acento e sem caixa."""
    import unicodedata

    def norm(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                       if unicodedata.category(c) != "Mn")

    t = norm(termo)
    if not t:
        return sorted(idx.values(), key=lambda s: s.nome)
    exatas = [s for s in idx.values() if t == norm(s.nome)]
    comeca = [s for s in idx.values() if norm(s.nome).startswith(t) and s not in exatas]
    contem = [s for s in idx.values()
              if (t in norm(s.nome) or t in norm(s.descricao))
              and s not in exatas and s not in comeca]
    return exatas + sorted(comeca, key=lambda s: s.nome) + sorted(contem, key=lambda s: s.nome)


# ------------------------------------------------------------- projetos --

@dataclass
class Projeto:
    nome: str
    raiz: Path

    def contexto(self, max_sessoes: int = 2) -> str:
        """Monta o 'onde paramos' seguindo o protocolo de leitura da skill.

        Deliberadamente NAO carrega o INDEX.md inteiro: sao 42 mil tokens, e a
        propria ADR 0008 do meta rebaixou o indice — a nota manda, o indice
        preenche lacuna.
        """
        partes = []
        ov = self.raiz / "_overview.md"
        if ov.is_file():
            partes.append(f"## Visao geral — {self.nome}\n\n"
                          + ov.read_text(encoding="utf-8", errors="replace").strip())
        st = self.raiz / "status.md"
        if st.is_file():
            partes.append(st.read_text(encoding="utf-8", errors="replace").strip())
        dir_ses = self.raiz / "sessoes"
        if dir_ses.is_dir():
            arqs = sorted((p for p in dir_ses.glob("*.md")), reverse=True)[:max_sessoes]
            for p in arqs:
                partes.append(f"## Sessao {p.stem}\n\n"
                              + p.read_text(encoding="utf-8", errors="replace").strip())
        if not partes:
            return ""
        return "\n\n---\n\n".join(partes)


def projetos(raiz_cerebro: str) -> dict[str, Projeto]:
    out: dict[str, Projeto] = {}
    base = Path(os.path.expanduser(raiz_cerebro or "")) / "projetos"
    if not base.is_dir():
        return out
    for p in sorted(base.iterdir()):
        if p.is_dir():
            out[p.name] = Projeto(nome=p.name, raiz=p)
    return out
