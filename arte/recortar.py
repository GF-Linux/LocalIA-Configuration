#!/usr/bin/env python3
"""Dissolve as bordas onde a figura é cortada pela moldura.

DIAGNÓSTICO, e o primeiro estava errado — vale registrar os dois:

  errado:  "a API deixou um fundo opaco; é só remover por preenchimento".
           O preenchimento comeu o manto, porque manto e suposto fundo são a
           mesma família de cor e estão conectados.

  certo:   a transparência ESTÁ correta — não há fundo. O que há é o manto
           SAINDO da tela: a última linha da `ritual` está 100% opaca, e as
           laterais 32-38%. O corte reto da moldura é o que lê como retângulo.

Então não se remove nada: dissolve-se. A base desaparece num degradê, que é o
que a própria referência do autor faz (a figura some em névoa embaixo).

O degradê é POR PONTILHADO ORDENADO, não por alfa parcial. Dois motivos: o
sixel trata transparência como liga/desliga, e meio-tom de alfa viraria uma
borda cinza suja; e pontilhado é a convenção de pixel art para degradê, então
o resultado continua parecendo desenhado, não borrado.

  python3 arte/recortar.py --todos
  python3 arte/recortar.py ritual --base 0.34 --lados 0.10 --ver
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"

# Bayer 4x4 — limiares ordenados, o padrão clássico de pontilhado.
BAYER4 = [
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
]


def _curva(t: float) -> float:
    """t=0 na borda (some) → t=1 onde a figura fica intacta. Suave nas pontas."""
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def esfuma(im: Image.Image, base: float = 0.34, lados: float = 0.10,
           topo: float = 0.0) -> tuple[Image.Image, int]:
    """Dissolve as bordas por pontilhado. (imagem, pixels apagados)."""
    im = im.convert("RGBA")
    W, H = im.size
    px = im.load()
    n_base = int(H * base)
    n_lado = int(W * lados)
    n_topo = int(H * topo)
    apagados = 0

    for y in range(H):
        for x in range(W):
            p = px[x, y]
            if p[3] <= 10:
                continue
            manter = 1.0
            if n_base and y >= H - n_base:
                manter = min(manter, _curva((H - 1 - y) / n_base))
            if n_topo and y < n_topo:
                manter = min(manter, _curva(y / n_topo))
            if n_lado:
                if x < n_lado:
                    manter = min(manter, _curva(x / n_lado))
                if x >= W - n_lado:
                    manter = min(manter, _curva((W - 1 - x) / n_lado))
            if manter >= 1.0:
                continue
            limiar = (BAYER4[y % 4][x % 4] + 0.5) / 16.0
            if manter <= limiar:
                px[x, y] = (p[0], p[1], p[2], 0)
                apagados += 1
    return im, apagados


def apara(im: Image.Image) -> Image.Image:
    caixa = im.getbbox()
    return im.crop(caixa) if caixa else im


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nomes", nargs="*")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--base", type=float, default=0.34,
                    help="fração da altura que dissolve embaixo")
    ap.add_argument("--lados", type=float, default=0.10,
                    help="fração da largura que dissolve nas laterais")
    ap.add_argument("--topo", type=float, default=0.0)
    ap.add_argument("--sufixo", default="")
    a = ap.parse_args()

    alvos = ([p.stem for p in sorted(SAIDA.glob("*.png"))
              if not p.stem.endswith(("-busto", "-cru"))]
             if a.todos else a.nomes)
    if not alvos:
        ap.print_help()
        return 1

    for nome in alvos:
        origem = SAIDA / f"{nome}.png"
        if not origem.exists():
            print(f"  {nome}: não existe")
            continue
        # guarda o original uma única vez, para poder refazer com outro ajuste
        cru = SAIDA / f"{nome}-cru.png"
        if not cru.exists():
            Image.open(origem).save(cru)
        im = Image.open(cru)
        antes = im.size
        saida, n = esfuma(im, a.base, a.lados, a.topo)
        saida = apara(saida)
        saida.save(SAIDA / f"{nome}{a.sufixo}.png")
        borda_base = sum(1 for x in range(saida.width)
                         if saida.getpixel((x, saida.height - 1))[3] > 10)
        print(f"  {nome:<12} {antes} → {saida.size}  {n} px dissolvidos  "
              f"base opaca: {100*borda_base/saida.width:.0f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
