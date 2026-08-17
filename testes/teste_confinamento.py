#!/usr/bin/env python3
"""O confinamento de caminho, testado contra tentativas de fuga.

Este teste existe por causa da ADR 0021 do autor: a trava so vale se o link
simbolico for RESOLVIDO antes da comparacao. Um `resultados.csv` apontando para
`~/.ssh/id_rsa` tem de ser recusado, e e o caso que um teste ingenuo nao cobre.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nucleo import ferramentas as F  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="jared-conf-"))
    raiz = tmp / "trabalho"
    (raiz / "sub").mkdir(parents=True)
    (raiz / "amostra.txt").write_text("dado do lab")
    (tmp / "fora.txt").write_text("SEGREDO")
    os.symlink(tmp / "fora.txt", raiz / "link-traicoeiro.txt")
    os.symlink(tmp, raiz / "fora-inteira")

    ctx = F.Contexto(raiz=raiz, auto_leitura=True)
    casos = [
        ("dentro, normal",           "amostra.txt",           True),
        ("subpasta",                 "sub",                   True),
        ("link simbolico p/ fora",   "link-traicoeiro.txt",   False),
        ("link p/ pasta de fora",    "fora-inteira/fora.txt", False),
        ("relativo subindo",         "../fora.txt",           False),
        ("absoluto fora",            "/etc/passwd",           False),
        ("til expandido",            "~/.ssh",                False),
    ]

    print(f"{'caso':<26} {'esperado':>9} {'obtido':>9}")
    print("-" * 48)
    falhas = 0
    for rotulo, caminho, deve_passar in casos:
        try:
            F._resolve(ctx, caminho)
            passou = True
        except F.Recusa:
            passou = False
        marca = "passa" if passou else "recusa"
        esp = "passa" if deve_passar else "recusa"
        ruim = passou != deve_passar
        print(f"{rotulo:<26} {esp:>9} {marca:>9}" + ("   <-- ERRADO" if ruim else ""))
        falhas += ruim

    shutil.rmtree(tmp, ignore_errors=True)
    print()
    if falhas:
        print(f"{falhas} FALHA(S) — nao use as ferramentas ate consertar")
        return 1
    print("confinamento ok: 7/7")
    return 0


if __name__ == "__main__":
    sys.exit(main())
