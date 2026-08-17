#!/usr/bin/env python3
"""Desenha o que o terminal desenharia, para conferir sem estar nele.

Interpreta a saída de `desenhar.py` como um terminal interpreta: célula por
célula, com `▀` pintando a metade de cima na cor de frente e a metade de baixo
na cor de fundo — e, quando não há cor de fundo declarada, deixando o fundo
REAL do terminal aparecer.

É essa última parte que se quer verificar. Se sobrar retângulo aqui, sobra lá.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent
RENDER = RAIZ / "render"

CEL_L, CEL_A = 9, 20          # métricas de célula do Konsole
SGR = re.compile(r"\033\[([0-9;]*)m")


def _aplica(codigo: str, fg, bg):
    partes = [p for p in codigo.split(";") if p != ""] or ["0"]
    i = 0
    while i < len(partes):
        p = partes[i]
        if p == "0":
            fg, bg = None, None
        elif p == "39":
            fg = None
        elif p == "49":
            bg = None
        elif p == "38" and i + 4 < len(partes) and partes[i+1] == "2":
            fg = tuple(int(x) for x in partes[i+2:i+5]); i += 4
        elif p == "48" and i + 4 < len(partes) and partes[i+1] == "2":
            bg = tuple(int(x) for x in partes[i+2:i+5]); i += 4
        i += 1
    return fg, bg


def _reverso():
    """caractere -> (sx, sy, bits). Monta dos próprios MODOS, sem duplicar
    tabela — se o renderizador mudar, o simulador acompanha."""
    import sys as _s
    _s.path.insert(0, str(RAIZ))
    from blocos import MODOS
    rev = {}
    for nome, (sx, sy, glifos) in MODOS.items():
        for bits, ch in glifos.items():
            if ch == " ":
                continue
            # o mais fino ganha quando o mesmo caractere serve a dois modos
            if ch not in rev or sx * sy > rev[ch][0] * rev[ch][1]:
                rev[ch] = (sx, sy, bits)
    return rev


REV = None


def simula(txt: str, fundo=(14, 15, 24), cols: int = 0) -> Image.Image:
    global REV
    if REV is None:
        REV = _reverso()
    linhas = txt.split("\n")
    if not cols:
        cols = max((len(SGR.sub("", l)) for l in linhas), default=1) + 2
    im = Image.new("RGB", (cols * CEL_L, len(linhas) * CEL_A), fundo)
    d = ImageDraw.Draw(im)
    try:
        fonte = ImageFont.truetype(
            "/usr/share/fonts/google-noto/NotoSansMono-Regular.ttf", 15)
    except OSError:
        fonte = None

    for ly, linha in enumerate(linhas):
        fg = bg = None
        col = 0
        i = 0
        while i < len(linha):
            m = SGR.match(linha, i)
            if m:
                fg, bg = _aplica(m.group(1), fg, bg)
                i = m.end()
                continue
            ch = linha[i]; i += 1
            x0, y0 = col * CEL_L, ly * CEL_A
            if bg is not None:
                d.rectangle([x0, y0, x0 + CEL_L - 1, y0 + CEL_A - 1], fill=bg)
            if ch in REV and fg is not None:
                sx, sy, bits = REV[ch]
                for k in range(sx * sy):
                    if not (bits >> k & 1):
                        continue
                    cx, cy = k % sx, k // sx
                    ax0 = x0 + round(cx * CEL_L / sx)
                    ax1 = x0 + round((cx + 1) * CEL_L / sx) - 1
                    ay0 = y0 + round(cy * CEL_A / sy)
                    ay1 = y0 + round((cy + 1) * CEL_A / sy) - 1
                    d.rectangle([ax0, ay0, ax1, ay1], fill=fg)
            elif ch != " " and fonte is not None:
                d.text((x0, y0 + 2), ch, fill=fg or (200, 200, 195), font=fonte)
            col += 1
    return im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nome")
    ap.add_argument("--saida", default="/tmp/simulado.png")
    ap.add_argument("--zoom", type=int, default=1)
    a = ap.parse_args()
    p = RENDER / f"{a.nome}.celulas"
    if not p.exists():
        raise SystemExit(f"não existe: {p} — rode desenhar.py antes")
    im = simula(p.read_text(encoding="utf-8"))
    if a.zoom > 1:
        im = im.resize((im.width * a.zoom, im.height * a.zoom), Image.NEAREST)
    im.save(a.saida)
    print(a.saida, im.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
