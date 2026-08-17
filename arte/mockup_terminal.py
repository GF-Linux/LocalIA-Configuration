#!/usr/bin/env python3
"""Montagem de como a abertura fica no terminal.

NÃO é captura de tela — é composição. O PNG entra a 1:1 (um pixel da arte = um
pixel da imagem, que é o que o sixel faz) e o texto é desenhado em monoespaçada
com as métricas de célula do Konsole. Serve para dar dimensão a quem está longe
da máquina; a palavra final é o terminal de verdade.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"
FONTE = "/usr/share/fonts/google-noto/NotoSansMono-Regular.ttf"

# Konsole com Noto Sans Mono 11pt a 96dpi: ~9 x 20 px por célula.
CEL_L, CEL_A = 9, 20
PT = 15

# Paleta escura de terminal
FUNDO = (14, 15, 24)   # medido no print do autor (#0e0f18)
INK = (232, 234, 232)
FRACO = (120, 126, 122)
ACENTO = (196, 160, 96)
VERDE = (110, 170, 130)


def texto(d, x, y, s, cor, fonte):
    d.text((x, y), s, fill=cor, font=fonte)


def compoe(nome_arte: str, busto: bool, titulo: str) -> Image.Image:
    png = SAIDA / (f"{nome_arte}-busto.png" if busto else f"{nome_arte}.png")
    arte = Image.open(png).convert("RGBA")

    cols, linhas = 78, arte.height // CEL_A + 11
    W, H = cols * CEL_L, linhas * CEL_A
    im = Image.new("RGB", (W, H), FUNDO)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONTE, PT)
    fb = ImageFont.truetype(FONTE, PT)

    y = CEL_A
    texto(d, CEL_L, y, "$ jared", VERDE, f)
    y += CEL_A * 2

    # A arte entra a 1:1 — um pixel da arte, um pixel da tela. E o texto vem
    # ABAIXO, empilhado, porque e isso que o sixel faz: ele deixa o cursor sob
    # a imagem. Por texto ao lado seria preciso salvar/restaurar cursor e
    # contar linhas de celula, que muda com o tamanho da fonte — banner que
    # quebra quando se aumenta a fonte nao serve.
    im.paste(arte, (CEL_L * 2, y), arte)
    y += arte.height + CEL_A

    tx = CEL_L * 2
    texto(d, tx, y, "jared", INK, fb)
    texto(d, tx + CEL_L * 6, y, "·", FRACO, f)
    texto(d, tx + CEL_L * 8, y, "qwen3.8:27b · local", INK, f)
    y += CEL_A
    texto(d, tx, y, "ctx 16k · ferramentas off", FRACO, f)
    y += CEL_A
    texto(d, tx, y, "/ajuda para os comandos · Ctrl-D para sair", FRACO, f)
    y += CEL_A * 2

    texto(d, CEL_L, y, "você", INK, fb)
    texto(d, CEL_L * 6, y, "›", ACENTO, fb)
    d.rectangle([CEL_L * 8, y + 3, CEL_L * 8 + CEL_L - 2, y + PT + 3],
                fill=(90, 94, 91))

    # rótulo discreto, fora da "tela"
    d.text((W - 240, 6), titulo, fill=(70, 74, 71), font=f)
    return im


def main() -> int:
    nome = sys.argv[1] if len(sys.argv) > 1 else "ritual"
    a = compoe(nome, busto=False, titulo="corpo inteiro · 1:1")
    b = compoe(nome, busto=True, titulo="busto · 1:1")
    pad = 18
    W = max(a.width, b.width)
    folha = Image.new("RGB", (W, a.height + b.height + pad), (8, 9, 8))
    folha.paste(a, (0, 0))
    folha.paste(b, (0, a.height + pad))
    alvo = f"/tmp/mockup_{nome}.png"
    folha.save(alvo)
    print(alvo, folha.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
