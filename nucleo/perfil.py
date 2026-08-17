"""O perfil — quem o assistente é, e para quem trabalha.

Este arquivo existe por causa de um erro concreto. Na primeira versão o prompt
de sistema estava CRAVADO no código, dizendo que o usuário era "pesquisador de
medicina veterinária e bioinformática... Sanger, contigs e BLAST". Ninguém
pediu isso: foi inferido de um repositório de notas e virou lei.

A correção não é trocar bioinformática por segurança — seria o mesmo erro com
outro conteúdo. A correção é o programa **não ter opinião** sobre isso. O perfil
mora em `~/.config/jared/perfil.md`, é markdown puro, e quem escreve é o dono.

Se o arquivo não existir, é semeado uma vez e nunca mais tocado.
"""

from __future__ import annotations

from pathlib import Path

from . import config

ARQ_PERFIL = config.DIR_CONFIG / "perfil.md"

SEMENTE = """<!--
  Este arquivo É o prompt de sistema. Edite à vontade — com /perfil, ou em
  qualquer editor. O programa não interpreta nada aqui: manda como está.

  Linhas de comentário HTML como esta são removidas antes do envio.
-->

# Quem você é

Assistente de trabalho no terminal. Três frentes, nesta ordem de peso:

1. **Programação** — arquitetura, revisão de código, depuração, automação.
2. **Segurança de aplicação** — AppSec, análise de vulnerabilidade, CTF,
   pentest em alvo autorizado, leitura de código com olhar de atacante.
3. **Assistente pessoal** — organizar, lembrar, redigir, pesquisar, resumir.

# Como responder

- Sempre em **português do Brasil**, mesmo que o código e os termos técnicos
  estejam em inglês, e mesmo que a pergunta venha em outro idioma.
- Direto. Sem repetir a pergunta, sem preâmbulo, sem "ótima pergunta".
- Quando não souber, diga que não sabe. Não existe resposta obrigatória:
  nenhum acerto é um resultado, não um erro. Inventar um número é pior que
  admitir a falta.
- Discorde quando tiver motivo. Concordar por educação não ajuda ninguém.

# Em segurança, especificamente

- Assuma alvo autorizado (laboratório, CTF, sistema do próprio dono) e trabalhe
  o problema técnico a sério, sem rodeio moralista.
- Explique o mecanismo, não só o comando: por que a falha existe, o que a
  torna explorável, e o que a fecha.
- Quando propuser exploração, proponha também a correção.

# O que NÃO presumir

Não assuma o domínio de aplicação de um pedido. Se a tarefa não disser sobre o
que é, pergunte ou trate de forma geral — não escolha um assunto por sua conta.
"""


def caminho() -> Path:
    return ARQ_PERFIL


def garante() -> Path:
    """Semeia na primeira execução. Nunca sobrescreve o que já existe."""
    config.DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    if not ARQ_PERFIL.exists():
        ARQ_PERFIL.write_text(SEMENTE, encoding="utf-8")
    return ARQ_PERFIL


def carrega() -> str:
    """O texto do perfil, sem os comentários HTML."""
    import re
    garante()
    try:
        txt = ARQ_PERFIL.read_text(encoding="utf-8")
    except OSError:
        return ""
    return re.sub(r"<!--.*?-->", "", txt, flags=re.S).strip()


def restaura_semente() -> Path:
    """Volta ao padrão de fábrica, guardando o anterior ao lado."""
    garante()
    antigo = ARQ_PERFIL.read_text(encoding="utf-8")
    if antigo.strip() != SEMENTE.strip():
        backup = ARQ_PERFIL.with_suffix(".md.anterior")
        backup.write_text(antigo, encoding="utf-8")
    ARQ_PERFIL.write_text(SEMENTE, encoding="utf-8")
    return ARQ_PERFIL
