#!/usr/bin/env python3
"""Desenha a arte com as CÉLULAS do terminal, não como imagem colada.

Por que existe, depois de duas rodadas erradas:

  sixel é uma imagem colada. O terminal reserva um retângulo e pinta raster
  dentro dele. Por mais que se acerte a cor do fundo, o retângulo existe — e o
  Konsole ainda o preenche com o registro de cor 0. Dois prints do autor
  mostraram a caixa, e a descrição dele foi exata: *"é como se o PNG estivesse
  control C control V, e não fazendo parte do terminal na sua constituição"*.

A saída daqui não é imagem: é TEXTO. Cada célula vira um `▀` com cor de frente
(metade de cima) e cor de fundo (metade de baixo) — dois pixels por célula.

E o ponto que resolve o problema: **onde é transparente, nenhuma cor é
emitida**. Metade de baixo vazia => sem código de fundo, e o fundo real do
terminal aparece ali. Célula inteira vazia => um espaço sem cor nenhuma.
Não há retângulo porque não há nada desenhado fora da figura.

Consequência aceita: a resolução passa a ser a da grade do terminal, não a da
imagem. Uma célula é um pixel-largura por dois pixels-altura, então a figura
inteira cabe em ~30 colunas. Menos detalhe que o sixel, e integrada de verdade.

  python3 arte/desenhar.py ritual --colunas 30
  python3 arte/desenhar.py --todos --colunas 30
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"
RENDER = RAIZ / "render"

RESET = "\033[0m"
ALFA_MIN = 10          # abaixo disso, o pixel não existe
BLOCO_CIMA = "▀"       # preenche a metade de cima da célula
BLOCO_BAIXO = "▄"


def _reduz(im: Image.Image, colunas: int) -> Image.Image:
    """NEAREST sempre: interpolar borraria a arte (medido — LANCZOS inventava
    2 496 cores numa paleta de 64)."""
    if colunas >= im.width:
        return im
    alt = max(2, round(im.height * colunas / im.width))
    if alt % 2:
        alt += 1                      # par: cada célula come 2 linhas
    return im.resize((colunas, alt), Image.NEAREST)


def desenha(png: Path, colunas: int = 30, margem: int = 2,
            base: float = 0.0, lados: float = 0.0) -> str:
    """base/lados > 0 dissolvem as bordas DEPOIS da redução.

    A ordem importa e custou uma rodada: dissolver a 132 px e reduzir para 30
    destrói o pontilhado — ele vira ruído, porque o padrão de 4x4 pixels não
    sobrevive a uma redução de 4x. Dissolvendo no tamanho final, cada ponto do
    pontilhado é uma célula inteira e o degradê lê como degradê.
    """
    im = _reduz(Image.open(png).convert("RGBA"), colunas)
    if base or lados:
        import sys as _s
        _s.path.insert(0, str(RAIZ))
        from recortar import esfuma
        im, _ = esfuma(im, base=base, lados=lados)
    W, H = im.size
    px = im.load()
    if H % 2:
        H -= 1

    linhas = []
    for y in range(0, H, 2):
        # apara a direita: célula vazia no fim não precisa ser escrita
        ultima = -1
        for x in range(W):
            if px[x, y][3] > ALFA_MIN or px[x, y + 1][3] > ALFA_MIN:
                ultima = x
        if ultima < 0:
            linhas.append("")
            continue

        buf = [" " * margem]
        fg_atual = bg_atual = None
        for x in range(ultima + 1):
            cima, baixo = px[x, y], px[x, y + 1]
            tem_c = cima[3] > ALFA_MIN
            tem_b = baixo[3] > ALFA_MIN

            if not tem_c and not tem_b:
                # NADA desenhado: sem cor de frente, sem cor de fundo.
                # É isto que faz o terminal aparecer no lugar.
                if fg_atual is not None or bg_atual is not None:
                    buf.append(RESET)
                    fg_atual = bg_atual = None
                buf.append(" ")
                continue

            if tem_c and tem_b:
                fg, bg, glifo = cima[:3], baixo[:3], BLOCO_CIMA
            elif tem_c:
                fg, bg, glifo = cima[:3], None, BLOCO_CIMA
            else:
                fg, bg, glifo = baixo[:3], None, BLOCO_BAIXO

            cod = []
            if bg is None and bg_atual is not None:
                cod.append("49")              # volta ao fundo do terminal
                bg_atual = None
            if fg != fg_atual:
                cod.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}")
                fg_atual = fg
            if bg is not None and bg != bg_atual:
                cod.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}")
                bg_atual = bg
            if cod:
                buf.append("\033[" + ";".join(cod) + "m")
            buf.append(glifo)

        buf.append(RESET)
        linhas.append("".join(buf))

    # tira linhas vazias das pontas
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    while linhas and not linhas[-1].strip():
        linhas.pop()
    return "\n".join(linhas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nomes", nargs="*")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--colunas", type=int, default=30)
    ap.add_argument("--margem", type=int, default=2)
    ap.add_argument("--base", type=float, default=0.0,
                    help="dissolve a base DEPOIS de reduzir (ex: 0.30)")
    ap.add_argument("--lados", type=float, default=0.0)
    ap.add_argument("--ver", action="store_true", help="imprime em vez de gravar")
    a = ap.parse_args()

    alvos = ([p.stem for p in sorted(SAIDA.glob("*.png"))
              if not p.stem.endswith("-cru")]
             if a.todos else a.nomes)
    if not alvos:
        ap.print_help()
        return 1

    RENDER.mkdir(parents=True, exist_ok=True)
    for nome in alvos:
        # prefere o original: a dissolução acontece DEPOIS de reduzir, então
        # partir de uma versão já dissolvida a 132 px só empilharia ruído
        png = SAIDA / f"{nome}-cru.png"
        if not png.exists():
            png = SAIDA / f"{nome}.png"
        if not png.exists():
            print(f"  {nome}: não existe")
            continue
        txt = desenha(png, a.colunas, a.margem, a.base, a.lados)
        if a.ver:
            print(txt)
            continue
        alvo = RENDER / f"{nome}.celulas"
        alvo.write_text(txt, encoding="utf-8")
        n_bg = txt.count("48;2;")
        print(f"  {nome:<16} {a.colunas} col × {len(txt.splitlines())} linhas  "
              f"({len(txt)} b, {n_bg} células com fundo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
