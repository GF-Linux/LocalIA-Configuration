#!/usr/bin/env python3
"""PNG → arte de terminal, sem borrar.

REGRA CENTRAL, e ela custou uma rodada: pixel art **não se reduz com
interpolação**. LANCZOS calcula a média dos vizinhos e apaga exatamente as
bordas duras que fazem a arte ler — o resultado foi descrito pelo dono como
"ainda está desfocada", e estava.

Comparadas as quatro formas na mesma imagem:

    LANCZOS /4   mingau borrado          <- o erro
    NEAREST /4   nítido, mas quebra demais
    NEAREST /2   legível e nítido        <- queda aceitável
    1:1 (sixel)  fidelidade total        <- o alvo

Daí as duas saídas:

  sixel      1:1 real, sem reamostragem nenhuma (Konsole 24+, foot, wezterm)
  meio-bloco redução NEAREST em razão INTEIRA, padrão /2

  python3 arte/render.py --todos
  python3 arte/render.py --ver ritual --sixel
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"
RENDER = RAIZ / "render"

# O chafa emite limpa-tela e vai-ao-topo mesmo com --clear=off. Impresso no
# arranque do jared, isso APAGARIA o terminal de quem abriu.
LIXO = re.compile(r"\033\[\?25[lh]|\033\[2J|\033\[\d*H")

DIVISOR_PADRAO = 2      # razão inteira de redução para meio-bloco


def achata(png: Path, cor: str) -> Path:
    """Compoe a arte sobre a cor do terminal e devolve um PNG temporario.

    Por que nao basta a transparencia, medido no print do autor:

      - o sixel do chafa JA declara fundo transparente (P2=1 no cabecalho);
      - o Konsole ignora isso e pinta a tela inteira do sixel com o registro
        de cor 0 — dentro da caixa o "transparente" virou (2,0,0), fora dela o
        fundo do terminal seguia (14,15,24);
      - `--bg` do chafa NAO tem efeito no formato sixel (testado: a paleta sai
        identica com e sem), e `--bg none` e erro.

    Entao o retangulo e inevitavel. O que se faz e torna-lo invisivel: se ele
    tem exatamente a cor do terminal, ninguem o ve. O custo e ter de refazer
    quando o tema mudar — e para isso existe a deteccao por OSC 11.
    """
    from PIL import Image
    im = Image.open(png).convert("RGBA")
    r, g, b = (int(cor.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    fundo = Image.new("RGBA", im.size, (r, g, b, 255))
    fundo.alpha_composite(im)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fundo.convert("RGB").save(tmp.name)
    return Path(tmp.name)


def tem_chafa() -> bool:
    return shutil.which("chafa") is not None


def _roda(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"chafa falhou: {r.stderr[:300]}")
    return LIXO.sub("", r.stdout).strip("\n")


def sixel(png: Path, cor_fundo: str = "") -> str:
    """1:1 — nenhuma reamostragem. É o melhor que o terminal permite."""
    if not tem_chafa():
        raise SystemExit("chafa não encontrado (dnf install chafa)")
    alvo = achata(png, cor_fundo) if cor_fundo else png
    try:
        return _roda(["chafa", "--format", "sixel", "--scale", "1",
                      "--exact-size", "on", "--clear=off", str(alvo)])
    finally:
        if alvo is not png:
            alvo.unlink(missing_ok=True)


def meio_bloco(png: Path, divisor: int = DIVISOR_PADRAO,
               cor_fundo: str = "") -> tuple[str, tuple]:
    """Redução NEAREST em razão inteira, e o chafa proibido de reamostrar."""
    if not tem_chafa():
        raise SystemExit("chafa não encontrado (dnf install chafa)")
    from PIL import Image
    im = Image.open(png).convert("RGBA")
    if cor_fundo:
        r, g, b = (int(cor_fundo.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        f = Image.new("RGBA", im.size, (r, g, b, 255))
        f.alpha_composite(im)
        im = f
    larg, alt = max(1, im.width // divisor), max(1, im.height // divisor)
    reduzida = im.resize((larg, alt), Image.NEAREST)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        reduzida.save(tmp.name)
        caminho = tmp.name
    try:
        # NAO usar --exact-size aqui: medido, ele encolhe 66x100 para 5 linhas
        # em vez de 50. Com --size batendo exatamente (larg colunas x alt/2
        # linhas) o mapeamento ja e 1:1 e o chafa nao reamostra nada.
        txt = _roda(["chafa", "--format", "symbols", "--symbols", "vhalf",
                     "--colors", "256", "--dither", "none", "--clear=off",
                     "--size", f"{larg}x{(alt + 1) // 2}", caminho])
    finally:
        Path(caminho).unlink(missing_ok=True)
    return txt, (larg, alt)


def todos(divisor: int, cor_fundo: str = "") -> int:
    if not SAIDA.is_dir():
        raise SystemExit(f"nada em {SAIDA} — rode arte/gerar.py primeiro")
    pngs = sorted(p for p in SAIDA.glob("*.png"))
    if not pngs:
        raise SystemExit(f"nenhum .png em {SAIDA}")
    RENDER.mkdir(parents=True, exist_ok=True)
    for p in pngs:
        txt, (l, a) = meio_bloco(p, divisor, cor_fundo)
        (RENDER / f"{p.stem}.ansi").write_text(txt, encoding="utf-8")
        sx = sixel(p, cor_fundo)
        (RENDER / f"{p.stem}.sixel").write_text(sx, encoding="utf-8")
        print(f"  {p.stem:<16} meio-bloco {l}x{a} px "
              f"({len(txt.splitlines())} linhas)  ·  sixel 1:1 "
              f"({len(sx)//1024} KiB)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--ver", default="")
    ap.add_argument("--sixel", action="store_true")
    ap.add_argument("--divisor", type=int, default=DIVISOR_PADRAO,
                    help="razão INTEIRA de redução do meio-bloco (2 = metade)")
    ap.add_argument("--fundo", default="",
                    help="cor de fundo do terminal (ex: #0e0f18). "
                         "Vazio = pergunta ao terminal por OSC 11.")
    a = ap.parse_args()

    sys.path.insert(0, str(RAIZ))
    from fundo import cor as detecta_cor
    cor_fundo, origem = detecta_cor(a.fundo)
    print(f"fundo do terminal: {cor_fundo}  ({origem})")

    if a.ver:
        png = SAIDA / f"{a.ver}.png"
        if not png.exists():
            raise SystemExit(f"não existe: {png}")
        print(sixel(png, cor_fundo) if a.sixel
              else meio_bloco(png, a.divisor, cor_fundo)[0])
        return 0
    if a.todos:
        return todos(a.divisor, cor_fundo)
    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
