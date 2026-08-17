"""Desenho no terminal.

Paleta monocromatica com um acento so, pela mesma razao da ADR 0005 da
Bancada: o que tem cor e o que importa — aqui, a proposta de ferramenta e o
aviso de que o modelo e remoto.

Nada de dependencia externa: a maquina nao tem pip.
"""

from __future__ import annotations

import os
import shutil
import sys

_TTY = sys.stdout.isatty()
_COR = _TTY and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"


def _c(codigo: str) -> str:
    return codigo if _COR else ""


RESET = _c("\033[0m")
NEGRITO = _c("\033[1m")
FRACO = _c("\033[2m")
ITALICO = _c("\033[3m")
# acento unico: ambar. usado so em proposta de acao e aviso.
ACENTO = _c("\033[38;5;179m")
PERIGO = _c("\033[38;5;174m")
OK = _c("\033[38;5;108m")
CINZA = _c("\033[38;5;245m")


def largura() -> int:
    return shutil.get_terminal_size((80, 24)).columns


def regra(char: str = "─") -> str:
    return FRACO + char * min(largura(), 78) + RESET


def diz(txt: str = "") -> None:
    print(txt)


def fraco(txt: str) -> None:
    print(f"{FRACO}{txt}{RESET}")


def aviso(txt: str) -> None:
    print(f"{ACENTO}⚠{RESET}  {txt}")


def erro(txt: str) -> None:
    print(f"{PERIGO}✗{RESET}  {txt}")


def bom(txt: str) -> None:
    print(f"{OK}✓{RESET}  {txt}")


def cabecalho(apelido: str, mod, cwd: str, ferramentas: bool, think: bool) -> None:
    """Barra de estado. Curta de proposito: ocupa a tela toda vez."""
    partes = [f"{NEGRITO}{apelido}{RESET}"]
    if mod.remoto:
        partes.append(f"{PERIGO}remoto{RESET}")
    else:
        partes.append(f"{CINZA}local{RESET}")
    partes.append(f"{CINZA}ctx {mod.n_ctx//1024}k{RESET}")
    if think:
        partes.append(f"{ACENTO}think{RESET}")
    if ferramentas:
        partes.append(f"{ACENTO}ferramentas{RESET}")
    curto = cwd.replace(str(os.path.expanduser("~")), "~")
    if len(curto) > 34:
        curto = "…" + curto[-33:]
    partes.append(f"{CINZA}{curto}{RESET}")
    print(f"{FRACO}·{RESET} " + f" {FRACO}·{RESET} ".join(partes))


def prompt() -> str:
    return f"{NEGRITO}você{RESET} {ACENTO}›{RESET} "


def marca_modelo(apelido: str) -> None:
    print(f"\n{CINZA}{apelido}{RESET} {FRACO}›{RESET} ", end="", flush=True)


def abre_pensamento() -> None:
    print(f"{FRACO}{ITALICO}", end="", flush=True)


def fecha_pensamento() -> None:
    print(f"{RESET}", end="", flush=True)


def corta(txt: str, max_linhas: int) -> str:
    linhas = txt.splitlines()
    if len(linhas) <= max_linhas:
        return txt
    resto = len(linhas) - max_linhas
    return "\n".join(linhas[:max_linhas]) + f"\n{FRACO}… (+{resto} linhas){RESET}"
