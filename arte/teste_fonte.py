#!/usr/bin/env python3
"""Mostra se a sua fonte tem os glifos dos modos mais finos.

Rode no terminal que você usa. Se aparecer quadradinho vazio, retângulo com
número dentro, ou espaço em branco onde deveria haver bloco, a fonte não tem
aquele conjunto — e aquele modo não serve para você.

  python3 arte/teste_fonte.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blocos import _sextante  # noqa: E402


def octante(v: int) -> str:
    """2x4 — bloco U+1CD00 (Unicode 16). Mapeamento parcial, só para o teste."""
    return chr(0x1CD00 + v)


def linha(rot: str, glifos: str) -> None:
    print(f"  {rot:<26} {glifos}")


def main() -> int:
    print("\nSe algum grupo aparecer como quadradinho vazio ou espaço,")
    print("sua fonte não tem aquele conjunto.\n")

    linha("meio-bloco (U+2580)", "▀▄█ ▌▐")
    linha("quadrante (U+2596)", "".join("▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"))
    linha("sextante (U+1FB00)", "".join(_sextante(v) for v in range(1, 21)))
    linha("sextante (mais)", "".join(_sextante(v) for v in range(43, 63)))
    linha("octante (U+1CD00)", "".join(octante(v) for v in range(0, 20)))

    print("\n  Referência — os três primeiros SEMPRE funcionam.")
    print("  Se o sextante funcionar, dá para usar --modo sextante")
    print("  (52×51 subpixels em vez de 52×34, mesma área de tela).\n")

    print("  Fontes instaladas aqui que têm sextante E octante:")
    print("    Adwaita Mono")
    print("    Cascadia Code NF")
    print("  A sua atual (JetBrainsMono Nerd Font) não tem nenhum dos dois.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
