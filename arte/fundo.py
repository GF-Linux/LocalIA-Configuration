#!/usr/bin/env python3
"""Descobre a cor de fundo do terminal.

Existe por um defeito visível: o `chafa` compõe a transparência sobre PRETO,
e o terminal do autor tem fundo `#0e0f18`. O resultado é um retângulo preto
nítido em volta da arte — medido no print dele, o fundo do terminal deu
(14,15,24) e o de dentro do retângulo (2,0,0).

A cor não pode ser cravada: quem troca de tema veria o mesmo defeito ao
contrário. Então pergunta-se ao terminal, por OSC 11.

  python3 arte/fundo.py            # imprime a cor detectada
"""

from __future__ import annotations

import os
import re
import select
import sys
import termios
import tty

# Se a consulta falhar, este é o palpite. Vem do print do autor, não de
# suposição — mas é palpite mesmo assim, e o programa diz quando usou.
PADRAO = "#0e0f18"

_RESP = re.compile(r"rgba?:([0-9a-f]{2,4})/([0-9a-f]{2,4})/([0-9a-f]{2,4})", re.I)


def consulta(timeout: float = 0.25) -> str | None:
    """Pergunta a cor de fundo ao terminal (OSC 11). None se não responder.

    O timeout é curto de propósito: terminal que não implementa OSC 11 fica
    calado, e um arranque pendurado é pior que uma cor errada.
    """
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None
    fd = sys.stdin.fileno()
    try:
        antigo = termios.tcgetattr(fd)
    except termios.error:
        return None
    try:
        tty.setraw(fd)
        sys.stdout.write("\033]11;?\033\\")
        sys.stdout.flush()
        buf = ""
        while True:
            pronto, _, _ = select.select([fd], [], [], timeout)
            if not pronto:
                break
            ped = os.read(fd, 64).decode("utf-8", "replace")
            if not ped:
                break
            buf += ped
            if "\033\\" in buf or "\a" in buf:
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, antigo)

    m = _RESP.search(buf)
    if not m:
        return None
    # o terminal pode responder em 16 bits por canal; fica com os 8 mais altos
    canais = []
    for g in m.groups():
        v = int(g[:2], 16) if len(g) >= 2 else int(g, 16)
        canais.append(v)
    return "#{:02x}{:02x}{:02x}".format(*canais)


def cor(preferida: str = "") -> tuple[str, str]:
    """(cor, origem). Ordem: o que o dono pediu > o terminal > o palpite."""
    if preferida:
        return preferida, "configurada"
    c = consulta()
    if c:
        return c, "detectada no terminal"
    return PADRAO, "palpite (o terminal não respondeu ao OSC 11)"


if __name__ == "__main__":
    c, origem = cor()
    print(f"{c}   ({origem})")
