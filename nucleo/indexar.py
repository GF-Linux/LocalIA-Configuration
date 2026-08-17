"""Regenera os índices dos acervos declarados em modelos.toml.

    python3 -m nucleo.indexar          # todos
    python3 -m nucleo.indexar h4cker   # um só
"""
import sys
from . import acervo, config


def main() -> int:
    cfg, aviso = config.carrega()
    if aviso:
        print(aviso); return 1
    alvo = sys.argv[1:] or list(cfg.acervos)
    if not cfg.acervos:
        print("nenhum acervo em [acervos] no modelos.toml"); return 1
    for nome in alvo:
        raiz = cfg.acervos.get(nome)
        if not raiz:
            print(f"  {nome}: não declarado"); continue
        ac = acervo.indexa(nome, raiz, com_pdf=nome in cfg.acervos_pdf)
        p = acervo.grava(ac)
        print(f"  {nome:<12} {len(ac.verbetes):>4} verbetes → {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
