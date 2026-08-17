#!/usr/bin/env python3
"""Desenho por QUADRANTES: 2x2 pixels por célula, em vez de 1x2.

Meio-bloco (`▀`) carrega um pixel de largura por célula. Quadrante carrega
DOIS. Para a mesma largura de tela, o dobro de resolução horizontal — que é
exatamente o pedido: *"diminuir o size e melhorar o desfocamento"*.

Os 16 glifos do bloco U+2580–259F cobrem todos os arranjos de 2x2, e são
Block Elements clássicos: suporte de fonte universal, sem depender de Nerd
Font nem de Legacy Computing.

A regra de transparência continua sendo a que resolveu o retângulo: subpixel
transparente vai para a metade de FUNDO do glifo e nenhuma cor de fundo é
emitida — o terminal aparece ali. Isso importa em dobro aqui, porque o Konsole
do autor tem IMAGEM de fundo: nenhuma cor achatada funcionaria.

Duas melhorias de nitidez que vêm junto:

  razão inteira  132/4 = 33 colunas exatas. A 34 a redução é 3,88x e descarta
                 pixels de forma irregular — é jitter, e lê como desfoque.
  cor dominante  cada bloco vira a cor MAIS COMUM dele, não a do canto
                 superior esquerdo. Amostrar um ponto joga fora 15 de 16
                 pixels e escolhe mal; a dominante preserva a forma.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"
RENDER = RAIZ / "render"

RESET = "\033[0m"
ALFA_MIN = 10

# Proporção da célula do terminal (largura/altura). Konsole com Noto Sans Mono
# fica em ~9/20. Entra na conta porque em quadrante cada subpixel mede
# CEL_L/2 x CEL_A/2 — 4,5 x 10 px de tela, MUITO mais alto que largo. Sem
# corrigir, a figura estica na vertical; foi o que aconteceu na 1a tentativa.
PROPORCAO_CELULA = 9 / 20

# bits: 1=sup-esq, 2=sup-dir, 4=inf-esq, 8=inf-dir
GLIFOS = {
    0b0000: " ", 0b0001: "▘", 0b0010: "▝", 0b0011: "▀",
    0b0100: "▖", 0b0101: "▌", 0b0110: "▞", 0b0111: "▛",
    0b1000: "▗", 0b1001: "▚", 0b1010: "▐", 0b1011: "▜",
    0b1100: "▄", 0b1101: "▙", 0b1110: "▟", 0b1111: "█",
}


def _lum(c) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def reduz_dominante(im: Image.Image, larg: int, alt: int) -> Image.Image:
    """Reduz pegando a cor DOMINANTE de cada bloco, não um ponto dele.

    NEAREST amostra um pixel e descarta o resto — numa redução de 4x isso
    joga fora 15 de 16 e a escolha é arbitrária. A dominante preserva a forma,
    e continua sem inventar cor (o valor devolvido existe no bloco).
    """
    W, H = im.size
    px = im.load()
    saida = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    sp = saida.load()
    for j in range(alt):
        y0, y1 = j * H // alt, max(j * H // alt + 1, (j + 1) * H // alt)
        for i in range(larg):
            x0, x1 = i * W // larg, max(i * W // larg + 1, (i + 1) * W // larg)
            conta = Counter()
            opacos = 0
            total = 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    p = px[x, y]
                    total += 1
                    if p[3] > ALFA_MIN:
                        opacos += 1
                        conta[p[:3]] += 1
            # o bloco só existe se a maioria dele existir
            if not conta or opacos * 2 < total:
                sp[i, j] = (0, 0, 0, 0)
            else:
                sp[i, j] = (*conta.most_common(1)[0][0], 255)
    return saida


def desenha(png: Path, colunas: int = 24, margem: int = 2,
            base: float = 0.0, lados: float = 0.0) -> str:
    im = Image.open(png).convert("RGBA")
    # cada célula come 2 pixels na horizontal e 2 na vertical
    larg = colunas * 2
    # preserva a proporção NA TELA, não na grade de pixels
    # alt = larg * (h/w) * (CEL_L/CEL_A). Derivação: a largura na tela é
    # larg*(CEL_L/2) e a altura alt*(CEL_A/2); igualar a razão à da imagem dá
    # esta fórmula. (Tinha um fator 2 sobrando e a figura saía o dobro de alta.)
    alt = round(larg * (im.height / im.width) * PROPORCAO_CELULA)
    if alt % 2:
        alt += 1
    im = reduz_dominante(im, larg, alt)

    if base or lados:
        import sys as _s
        _s.path.insert(0, str(RAIZ))
        from recortar import esfuma
        im, _ = esfuma(im, base=base, lados=lados)

    px = im.load()
    linhas = []
    for cy in range(0, alt, 2):
        ultima = -1
        for cx in range(0, larg, 2):
            if any(px[cx + dx, cy + dy][3] > ALFA_MIN
                   for dx in (0, 1) for dy in (0, 1)):
                ultima = cx
        if ultima < 0:
            linhas.append("")
            continue

        buf = [" " * margem]
        fg_at = bg_at = None
        for cx in range(0, ultima + 2, 2):
            quatro = [px[cx, cy], px[cx + 1, cy],
                      px[cx, cy + 1], px[cx + 1, cy + 1]]
            opacos = [(k, c) for k, c in enumerate(quatro) if c[3] > ALFA_MIN]

            if not opacos:
                if fg_at is not None or bg_at is not None:
                    buf.append(RESET); fg_at = bg_at = None
                buf.append(" ")
                continue

            if len(opacos) < 4:
                # há transparência: os opacos viram frente, o resto fica sem
                # cor de fundo — e o terminal (ou a imagem dele) aparece ali
                bits = sum(1 << k for k, _ in opacos)
                fg = _media([c for _, c in opacos])
                bg = None
            else:
                # todos opacos: separa em dois grupos por luminância
                lums = sorted(range(4), key=lambda k: _lum(quatro[k]))
                escuros = set(lums[:2]) if _spread(quatro) else set()
                if not escuros:
                    bits, fg, bg = 0b1111, _media(quatro), None
                else:
                    claros = [k for k in range(4) if k not in escuros]
                    bits = sum(1 << k for k in claros)
                    fg = _media([quatro[k] for k in claros])
                    bg = _media([quatro[k] for k in escuros])

            cod = []
            if bg is None and bg_at is not None:
                cod.append("49"); bg_at = None
            if fg != fg_at:
                cod.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}"); fg_at = fg
            if bg is not None and bg != bg_at:
                cod.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}"); bg_at = bg
            if cod:
                buf.append("\033[" + ";".join(cod) + "m")
            buf.append(GLIFOS[bits])

        buf.append(RESET)
        linhas.append("".join(buf))

    while linhas and not linhas[0].strip():
        linhas.pop(0)
    while linhas and not linhas[-1].strip():
        linhas.pop()
    return "\n".join(linhas)


def _media(cores) -> tuple:
    n = len(cores)
    return tuple(sum(c[i] for c in cores) // n for i in range(3))


def _spread(quatro, limiar: float = 18.0) -> bool:
    """Vale separar em dois grupos? Só se houver contraste real no bloco."""
    ls = [_lum(c) for c in quatro]
    return max(ls) - min(ls) > limiar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nomes", nargs="*")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--colunas", type=int, default=24)
    ap.add_argument("--margem", type=int, default=2)
    ap.add_argument("--base", type=float, default=0.28)
    ap.add_argument("--lados", type=float, default=0.06)
    ap.add_argument("--sufixo", default="")
    a = ap.parse_args()

    alvos = ([p.stem for p in sorted(SAIDA.glob("*-cru.png"))]
             if a.todos else a.nomes)
    if not alvos:
        ap.print_help()
        return 1

    RENDER.mkdir(parents=True, exist_ok=True)
    for nome in alvos:
        png = SAIDA / f"{nome}.png"
        if not png.exists():
            png = SAIDA / f"{nome}-cru.png"
        if not png.exists():
            print(f"  {nome}: não existe")
            continue
        txt = desenha(png, a.colunas, a.margem, a.base, a.lados)
        limpo = nome.replace("-cru", "")
        (RENDER / f"{limpo}{a.sufixo}.celulas").write_text(txt, encoding="utf-8")
        print(f"  {limpo:<14} {a.colunas} col × {len(txt.splitlines())} linhas  "
              f"(equivale a {a.colunas*2} px de largura)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
