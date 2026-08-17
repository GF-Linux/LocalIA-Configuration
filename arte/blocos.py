#!/usr/bin/env python3
"""Renderizador de blocos com busca do melhor símbolo.

Três modos, do mais compatível ao mais fiel:

  meio      1x2 subpixels por célula — U+2580, qualquer fonte
  quad      2x2 — Block Elements, qualquer fonte (é o que roda hoje)
  sextante  2x3 — U+1FB00, exige fonte com Legacy Computing

O ganho principal não é só o número de subpixels. É a ESCOLHA do símbolo.
A versão anterior separava o bloco por luminância — um chute razoável. Aqui
todos os padrões possíveis são testados (4, 16 ou 64) e fica o que minimiza o
erro de cor contra os subpixels reais. É o que o chafa faz, e a diferença
aparece em rosto e dobra de pano.

A regra de transparência é a mesma que resolveu o retângulo: subpixel
transparente entra no grupo de FUNDO e nenhuma cor de fundo é emitida — o
terminal (que no caso do autor tem imagem) aparece ali.
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
PROPORCAO_CELULA = 9 / 20     # largura/altura da célula (JetBrainsMono 11)

QUAD = {
    0b0000: " ", 0b0001: "▘", 0b0010: "▝", 0b0011: "▀",
    0b0100: "▖", 0b0101: "▌", 0b0110: "▞", 0b0111: "▛",
    0b1000: "▗", 0b1001: "▚", 0b1010: "▐", 0b1011: "▜",
    0b1100: "▄", 0b1101: "▙", 0b1110: "▟", 0b1111: "█",
}


def _sextante(v: int) -> str:
    """2x3. Bits: 1=sup-esq 2=sup-dir 4=meio-esq 8=meio-dir 16=inf-esq 32=inf-dir.

    Quatro valores moram fora do bloco U+1FB00 porque já existiam no Unicode:
    vazio, coluna esquerda, coluna direita e cheio.
    """
    if v == 0:
        return " "
    if v == 0b010101:
        return "▌"
    if v == 0b101010:
        return "▐"
    if v == 0b111111:
        return "█"
    i = v - 1 - (1 if v > 0b010101 else 0) - (1 if v > 0b101010 else 0)
    return chr(0x1FB00 + i)


def _octantes() -> dict:
    """2x4 — 256 padrões. A tabela é DERIVADA do banco Unicode do Python
    (16.0.0), não digitada: 230 saem do nome "BLOCK OCTANT-<posições>" e os 26
    restantes já existiam como meio-bloco, quadrante ou quarto de bloco.

    Grade e posições:   1 2 / 3 4 / 5 6 / 7 8
    """
    import unicodedata
    por_conj = {}
    for cp in range(0x1CD00, 0x1CDE6):
        try:
            n = unicodedata.name(chr(cp))
        except ValueError:
            continue
        if n.startswith("BLOCK OCTANT-"):
            por_conj[frozenset(int(d) for d in n.split("-")[1])] = chr(cp)
    # os que moram fora do bloco dos octantes
    por_conj.update({
        frozenset():                  " ",
        frozenset({1}):               "\U0001CEA8",
        frozenset({2}):               "\U0001CEAB",
        frozenset({1, 2}):            "\U0001FB82",
        frozenset({1, 3}):            "▘",
        frozenset({2, 4}):            "▝",
        frozenset({3, 5}):            "\U0001FBE6",
        frozenset({4, 6}):            "\U0001FBE7",
        frozenset({5, 7}):            "▖",
        frozenset({6, 8}):            "▗",
        frozenset({7}):               "\U0001CEA3",
        frozenset({8}):               "\U0001CEA0",
        frozenset({7, 8}):            "\u2582",
        frozenset({1, 2, 3, 4}):      "▀",
        frozenset({5, 6, 7, 8}):      "▄",
        frozenset({1, 3, 5, 7}):      "▌",
        frozenset({2, 4, 6, 8}):      "▐",
        frozenset({1, 3, 6, 8}):      "▚",
        frozenset({2, 4, 5, 7}):      "▞",
        frozenset({1, 2, 3, 4, 5, 6}): "\U0001FB85",
        frozenset({3, 4, 5, 6, 7, 8}): "\u2586",
        frozenset({1, 2, 3, 4, 5, 7}): "▛",
        frozenset({1, 2, 3, 4, 6, 8}): "▜",
        frozenset({1, 3, 5, 6, 7, 8}): "▙",
        frozenset({2, 4, 5, 6, 7, 8}): "▟",
        frozenset(range(1, 9)):        "█",
    })
    tabela = {}
    for v in range(256):
        conj = frozenset(p for p in range(1, 9) if v >> (p - 1) & 1)
        if conj not in por_conj:
            raise RuntimeError(f"padrão de octante sem caractere: {sorted(conj)}")
        tabela[v] = por_conj[conj]
    return tabela


MODOS = {
    "meio": (1, 2, {0b00: " ", 0b01: "▀", 0b10: "▄", 0b11: "█"}),
    "quad": (2, 2, QUAD),
    "sextante": (2, 3, {v: _sextante(v) for v in range(64)}),
    "octante": (2, 4, _octantes()),
}


def _media(cores):
    n = len(cores)
    return tuple(sum(c[i] for c in cores) // n for i in range(3))


def _erro(cor, alvo) -> float:
    dr, dg, db = cor[0]-alvo[0], cor[1]-alvo[1], cor[2]-alvo[2]
    return 2*dr*dr + 4*dg*dg + 3*db*db      # pondera o verde, como o olho


def reduz_dominante(im: Image.Image, larg: int, alt: int) -> Image.Image:
    """Cor dominante do bloco — não amostra um ponto e nem inventa cor nova."""
    W, H = im.size
    px = im.load()
    saida = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    sp = saida.load()
    for j in range(alt):
        y0, y1 = j*H//alt, max(j*H//alt + 1, (j+1)*H//alt)
        for i in range(larg):
            x0, x1 = i*W//larg, max(i*W//larg + 1, (i+1)*W//larg)
            conta, opacos, total = Counter(), 0, 0
            for y in range(y0, y1):
                for x in range(x0, x1):
                    p = px[x, y]
                    total += 1
                    if p[3] > ALFA_MIN:
                        opacos += 1
                        conta[p[:3]] += 1
            sp[i, j] = ((0, 0, 0, 0) if not conta or opacos*2 < total
                        else (*conta.most_common(1)[0][0], 255))
    return saida


def melhor_simbolo(sub: list, glifos: dict):
    """(bits, fg, bg). bg=None quando há transparência no bloco.

    Testa TODOS os padrões e fica com o de menor erro. Com n subpixels são
    2^n candidatos — 4, 16 ou 64. Barato, e melhor que qualquer heurística:
    a separação por luminância erra quando o contraste do bloco é de matiz.
    """
    n = len(sub)
    op = [k for k, c in enumerate(sub) if c[3] > ALFA_MIN]
    if not op:
        return 0, None, None

    if len(op) < n:
        # transparência manda: os opacos vão para a frente, o resto fica vazio
        bits = sum(1 << k for k in op)
        return bits, _media([sub[k] for k in op]), None

    melhor = None
    for bits in range(1, (1 << n) - 1 + 1):
        frente = [k for k in range(n) if bits >> k & 1]
        fundo = [k for k in range(n) if not (bits >> k & 1)]
        fg = _media([sub[k] for k in frente]) if frente else None
        bg = _media([sub[k] for k in fundo]) if fundo else None
        e = 0.0
        for k in frente:
            e += _erro(fg, sub[k])
        for k in fundo:
            e += _erro(bg, sub[k])
        if melhor is None or e < melhor[0]:
            melhor = (e, bits, fg, bg)
    _, bits, fg, bg = melhor
    return bits, fg, bg


def desenha(png: Path, colunas: int = 26, modo: str = "quad",
            margem: int = 2, base: float = 0.0, lados: float = 0.0,
            nativo: bool = False) -> str:
    sx, sy, glifos = MODOS[modo]
    im = Image.open(png).convert("RGBA")
    if nativo:
        # A arte JÁ está na resolução de exibição: qualquer redimensionamento
        # aqui só destruiria. É o modo certo quando o sprite foi gerado no
        # tamanho da grade — 52x68 = 26 colunas x 17 linhas em octante.
        larg, alt = im.width, im.height
        alt -= alt % sy
        larg -= larg % sx
        if (larg, alt) != im.size:
            im = im.crop((0, 0, larg, alt))
    else:
        larg = colunas * sx
        # proporção NA TELA: cada subpixel mede (CEL_L/sx) x (CEL_A/sy)
        alt = round(larg * (im.height/im.width) * PROPORCAO_CELULA * (sy/sx))
        alt = max(sy, alt - alt % sy)
        im = reduz_dominante(im, larg, alt)

    if base or lados:
        import sys as _s
        _s.path.insert(0, str(RAIZ))
        from recortar import esfuma
        im, _ = esfuma(im, base=base, lados=lados)

    px = im.load()
    linhas = []
    for cy in range(0, alt, sy):
        ultima = -1
        for cx in range(0, larg, sx):
            if any(px[cx+dx, cy+dy][3] > ALFA_MIN
                   for dx in range(sx) for dy in range(sy)):
                ultima = cx
        if ultima < 0:
            linhas.append("")
            continue

        buf = [" " * margem]
        fg_at = bg_at = None
        for cx in range(0, ultima + sx, sx):
            sub = [px[cx+dx, cy+dy] for dy in range(sy) for dx in range(sx)]
            bits, fg, bg = melhor_simbolo(sub, glifos)
            if fg is None:
                if fg_at is not None or bg_at is not None:
                    buf.append(RESET); fg_at = bg_at = None
                buf.append(" ")
                continue
            cod = []
            if bg is None and bg_at is not None:
                cod.append("49"); bg_at = None
            if fg != fg_at:
                cod.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}"); fg_at = fg
            if bg is not None and bg != bg_at:
                cod.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}"); bg_at = bg
            if cod:
                buf.append("\033[" + ";".join(cod) + "m")
            buf.append(glifos[bits])
        buf.append(RESET)
        linhas.append("".join(buf))

    while linhas and not linhas[0].strip():
        linhas.pop(0)
    while linhas and not linhas[-1].strip():
        linhas.pop()
    return "\n".join(linhas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nomes", nargs="*")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--modo", choices=list(MODOS), default="quad")
    ap.add_argument("--colunas", type=int, default=26)
    ap.add_argument("--margem", type=int, default=2)
    ap.add_argument("--base", type=float, default=0.28)
    ap.add_argument("--lados", type=float, default=0.06)
    ap.add_argument("--nativo", action="store_true",
                    help="a arte já está na resolução final; não redimensiona")
    ap.add_argument("--sufixo", default="")
    a = ap.parse_args()

    alvos = ([p.stem for p in sorted(SAIDA.glob("*.png"))
              if not p.stem.endswith(("-cru", "-busto"))]
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
            print(f"  {nome}: não existe"); continue
        txt = desenha(png, a.colunas, a.modo, a.margem, a.base, a.lados,
                      a.nativo)
        (RENDER / f"{nome}{a.sufixo}.celulas").write_text(txt, encoding="utf-8")
        sx, sy, _ = MODOS[a.modo]
        # em --nativo as colunas saem da ARTE, não do argumento; imprimir o
        # argumento aqui mentia (dizia 26 para uma arte de 39 colunas)
        import re as _re
        largura = max((len(_re.sub(r"\033\[[0-9;]*m", "", l))
                       for l in txt.splitlines()), default=0) - a.margem
        n_lin = len(txt.splitlines())
        print(f"  {nome:<16} {a.modo:<9} {largura} col × {n_lin} lin  "
              f"({largura*sx}×{n_lin*sy} subpixels)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
