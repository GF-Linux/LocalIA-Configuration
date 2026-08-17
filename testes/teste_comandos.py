#!/usr/bin/env python3
"""A triagem de comando, antes da confirmacao.

ADR 0020: sem shell por padrao. O que se testa aqui e a TRIAGEM — o que nem
chega a ser oferecido para confirmacao. A confirmacao e substituida por uma
recusa automatica, para isolar as duas coisas.
"""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from nucleo import ferramentas as F  # noqa: E402

TRIADO = "recusa na triagem"
OFERECIDO = "chega na confirmacao"

CASOS = [
    ("comando simples",      "ls -la",                 OFERECIDO),
    ("pipe",                 "cat a.txt | grep x",     TRIADO),
    ("redirecionamento",     "ls > saida.txt",         TRIADO),
    ("encadeamento",         "make && ./run",          TRIADO),
    ("ponto e virgula",      "ls; rm -rf /",           TRIADO),
    ("substituicao",         "echo $(whoami)",         TRIADO),
    ("crase",                "echo `id`",              TRIADO),
    ("interativo sem PTY",   "sudo dnf install x",     TRIADO),
    ("python pelado",        "python3",                TRIADO),
    ("escape declarado",     'bash -c "ls | wc -l"',   OFERECIDO),
]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="jared-cmd-"))
    ctx = F.Contexto(raiz=tmp)
    original = F._pergunta
    F._pergunta = lambda *a, **k: "nao"      # isola triagem de confirmacao

    print(f"{'caso':<24} {'esperado':<22} {'obtido'}")
    print("-" * 70)
    falhas = 0
    try:
        for rotulo, cmd, esperado in CASOS:
            saida, _ = F.executa(ctx, "executar", {"comando": cmd})
            if saida.startswith("recusado: o comando usa") or "interativo e travaria" in saida:
                obtido = TRIADO
            elif "a pessoa recusou" in saida:
                obtido = OFERECIDO
            else:
                obtido = saida[:38]
            ruim = obtido != esperado
            print(f"{rotulo:<24} {esperado:<22} {obtido}" + ("   <-- ERRADO" if ruim else ""))
            falhas += ruim
    finally:
        F._pergunta = original
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if falhas:
        print(f"{falhas} FALHA(S)")
        return 1
    print(f"triagem ok: {len(CASOS)}/{len(CASOS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
