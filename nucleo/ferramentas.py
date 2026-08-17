"""Ferramentas, confinamento e confirmacao.

As regras aqui nao foram inventadas: sao as que o autor ja estabeleceu nas
proprias ADRs, trazidas para o terminal.

  0021  link simbolico e RESOLVIDO antes de comparar. `resultados.csv`
        apontando para `~/.ssh/id_rsa` nao passa.
  0020  sem shell por padrao. `|`, `>`, `&&`, `;` sao recusados com explicacao;
        o escape e declarado (`bash -c "..."`) e aparece inteiro na tela.
  0035  o modelo PROPOE, quem aciona e a pessoa. Chave inventada nao vira acao.
  0013  fechar nao e excluir. Nao ha ferramenta que apague nada.

Duas travas a mais, aprendidas medindo:
  - a confirmacao mostra o COMANDO EXATO que vai rodar, ja dividido em
    argumentos, nao a intencao declarada pelo modelo;
  - escrever mostra o diff antes, e nunca cria arquivo fora da raiz.
"""

from __future__ import annotations

import difflib
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import tela

MAX_BYTES_LEITURA = 200_000
TIMEOUT_COMANDO = 120

# caracteres que so fazem sentido com shell; recusados com explicacao (ADR 0020)
METACARACTERES = ("|", ">", "<", "&&", "||", ";", "`", "$(", "\n")

# programas interativos travariam o REPL: sem PTY, ficam esperando para sempre
INTERATIVOS = {"sudo", "su", "htop", "top", "vim", "vi", "nano", "less",
               "more", "ssh", "python", "python3", "ipython", "psql", "mysql"}


SEM_TERMINAL = ("não há terminal interativo para confirmar esta ação, "
                "então ela não foi feita — ninguém recusou.")


class Recusa(Exception):
    """Recusa com motivo legivel — vira resposta de ferramenta para o modelo."""


@dataclass
class Contexto:
    raiz: Path                  # confinamento
    auto_leitura: bool = False  # ler/listar/buscar sem perguntar
    max_linhas: int = 60


# ------------------------------------------------------------ confinamento --

def _resolve(ctx: Contexto, caminho: str) -> Path:
    """Caminho absoluto, com link simbolico resolvido, dentro da raiz."""
    if not caminho or not caminho.strip():
        raise Recusa("caminho vazio")
    p = Path(os.path.expanduser(caminho.strip()))
    if not p.is_absolute():
        p = ctx.raiz / p
    # resolve() segue links simbolicos — e o ponto (ADR 0021)
    alvo = p.resolve()
    raiz = ctx.raiz.resolve()
    if alvo != raiz and raiz not in alvo.parents:
        raise Recusa(
            f"fora da pasta de trabalho. A raiz e {raiz}, e o caminho resolve "
            f"para {alvo}. Se for um link simbolico, ele foi seguido de "
            f"proposito.")
    return alvo


# ------------------------------------------------------------- confirmacao --

def _pergunta(titulo: str, corpo: str, perigo: bool = False) -> str:
    """Devolve 'sim' | 'nao' | 'editar' | 'sem_terminal'. A pessoa decide, sempre.

    **`sem_terminal` existe porque a recusa muda de sentido.** Sem stdin
    interativo — `jared` chamado de um script, de outro programa, ou com a
    entrada redirecionada — o `input()` levanta EOF na hora, toda ação é negada,
    e a mensagem dizia "a pessoa recusou". Não havia pessoa nenhuma: era o
    programa respondendo por ela e culpando-a pela recusa.

    Foi assim que uma tentativa de mandar o jared analisar um repositório
    "morreu antes de executar": ele propunha `listar`, a confirmação nascia
    negada, e o modelo seguia com um "ok, sem problema".
    """
    if not sys.stdin.isatty():
        return "sem_terminal"
    cor = tela.PERIGO if perigo else tela.ACENTO
    print()
    print(f"  {cor}⚡{tela.RESET} {tela.NEGRITO}{titulo}{tela.RESET}")
    for linha in corpo.splitlines():
        print(f"    {tela.CINZA}{linha}{tela.RESET}")
    print(f"    {tela.FRACO}[enter] fazer   [e] editar   [n] recusar{tela.RESET}")
    try:
        r = input("    › ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "nao"
    if r in ("", "s", "sim", "y"):
        return "sim"
    if r in ("e", "editar"):
        return "editar"
    return "nao"


# --------------------------------------------------------------- as acoes --

def f_listar(ctx: Contexto, args: dict) -> str:
    alvo = _resolve(ctx, args.get("caminho") or ".")
    if not alvo.exists():
        raise Recusa(f"nao existe: {alvo}")
    if alvo.is_file():
        return f"{alvo.name} — arquivo, {alvo.stat().st_size} bytes"
    linhas = []
    for p in sorted(alvo.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if p.is_dir():
            linhas.append(f"{p.name}/")
        else:
            linhas.append(f"{p.name}  ({p.stat().st_size} b)")
    return "\n".join(linhas) if linhas else "(pasta vazia)"


def f_ler(ctx: Contexto, args: dict) -> str:
    alvo = _resolve(ctx, args.get("caminho", ""))
    if not alvo.is_file():
        raise Recusa(f"nao e arquivo: {alvo}")
    tam = alvo.stat().st_size
    if tam > MAX_BYTES_LEITURA:
        raise Recusa(
            f"arquivo grande demais ({tam} bytes, teto {MAX_BYTES_LEITURA}). "
            f"Peca um trecho com a ferramenta buscar.")
    try:
        txt = alvo.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise Recusa(f"nao consegui ler: {e}") from None
    return txt if txt.strip() else "(arquivo vazio)"


def f_buscar(ctx: Contexto, args: dict) -> str:
    padrao = (args.get("padrao") or "").strip()
    if not padrao:
        raise Recusa("padrao vazio")
    alvo = _resolve(ctx, args.get("caminho") or ".")
    cmd = ["grep", "-rIn", "--color=never", "-m", "40", "--", padrao, str(alvo)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise Recusa("a busca demorou demais") from None
    if r.returncode not in (0, 1):
        raise Recusa(f"grep falhou: {r.stderr[:200]}")
    saida = r.stdout.strip()
    if not saida:
        # a ADR 0039 do autor, aplicada aqui: nenhum acerto e RESULTADO
        return f"nenhuma linha casa com {padrao!r} em {alvo}. Isso e um resultado, nao um erro."
    return tela.corta(saida, ctx.max_linhas)


def f_escrever(ctx: Contexto, args: dict) -> str:
    alvo = _resolve(ctx, args.get("caminho", ""))
    conteudo = args.get("conteudo")
    if conteudo is None:
        raise Recusa("faltou o conteudo")
    antigo = ""
    if alvo.exists():
        if not alvo.is_file():
            raise Recusa(f"nao e arquivo: {alvo}")
        antigo = alvo.read_text(encoding="utf-8", errors="replace")

    diff = "\n".join(difflib.unified_diff(
        antigo.splitlines(), str(conteudo).splitlines(),
        fromfile=f"{alvo.name} (atual)", tofile=f"{alvo.name} (proposto)",
        lineterm="", n=2))
    corpo = (diff or "(sem alteracao)") if antigo else \
        f"criar arquivo novo, {len(str(conteudo).splitlines())} linhas"

    r = _pergunta(f"escrever em {alvo}", tela.corta(corpo, 40), perigo=True)
    if r == "sem_terminal":
        raise Recusa(SEM_TERMINAL)
    if r == "editar":
        raise Recusa("a pessoa quis editar o conteudo — reformule a proposta")
    if r != "sim":
        raise Recusa("a pessoa recusou a escrita")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(str(conteudo), encoding="utf-8")
    return f"gravado: {alvo} ({len(str(conteudo))} bytes)"


def f_executar(ctx: Contexto, args: dict) -> str:
    bruto = (args.get("comando") or "").strip()
    if not bruto:
        raise Recusa("comando vazio")

    # ADR 0020: sem shell, com escape declarado
    usa_shell = False
    if bruto.startswith("bash -c ") or bruto.startswith("sh -c "):
        usa_shell = True
    else:
        for m in METACARACTERES:
            if m in bruto:
                raise Recusa(
                    f"o comando usa {m!r}, que so funciona com shell. Aqui nao "
                    f"ha shell por padrao. Se precisa mesmo, proponha "
                    f'explicitamente: bash -c "..." — e a pessoa vera o comando '
                    f"inteiro antes de autorizar.")
    try:
        partes = shlex.split(bruto)
    except ValueError as e:
        raise Recusa(f"nao consegui separar os argumentos: {e}") from None
    if not partes:
        raise Recusa("comando vazio depois de separar")

    programa = os.path.basename(partes[0])
    if programa in INTERATIVOS and not usa_shell:
        raise Recusa(
            f"{programa!r} e interativo e travaria aqui (nao ha terminal "
            f"virtual). Use a forma nao interativa, se houver.")

    mostrado = "\n".join(f"  argv[{i}] {a}" for i, a in enumerate(partes))
    r = _pergunta(f"executar em {ctx.raiz}", f"{bruto}\n{mostrado}", perigo=True)
    if r == "sem_terminal":
        raise Recusa(SEM_TERMINAL)
    if r == "editar":
        raise Recusa("a pessoa quis editar o comando — reformule a proposta")
    if r != "sim":
        raise Recusa("a pessoa recusou o comando")

    try:
        proc = subprocess.run(
            partes, cwd=str(ctx.raiz), capture_output=True, text=True,
            timeout=TIMEOUT_COMANDO,
            env={**os.environ, "PYTHONUNBUFFERED": "1"})
    except FileNotFoundError:
        raise Recusa(f"programa nao encontrado: {partes[0]!r}") from None
    except subprocess.TimeoutExpired:
        raise Recusa(f"passou de {TIMEOUT_COMANDO}s e foi interrompido") from None

    pedacos = [f"codigo de saida: {proc.returncode}"]
    if proc.stdout.strip():
        pedacos.append("stdout:\n" + tela.corta(proc.stdout.rstrip(), ctx.max_linhas))
    if proc.stderr.strip():
        pedacos.append("stderr:\n" + tela.corta(proc.stderr.rstrip(), 20))
    if not proc.stdout.strip() and not proc.stderr.strip():
        pedacos.append("(sem saida)")
    return "\n\n".join(pedacos)


# ------------------------------------------------------------ o catalogo --

ACOES = {
    "listar":   (f_listar,   False),   # (funcao, exige confirmacao sempre)
    "ler":      (f_ler,      False),
    "buscar":   (f_buscar,   False),
    "escrever": (f_escrever, True),    # confirma dentro da propria funcao
    "executar": (f_executar, True),
}

ESQUEMAS = [
    {"type": "function", "function": {
        "name": "listar",
        "description": "Lista o conteudo de uma pasta dentro da pasta de trabalho.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string",
                        "description": "pasta a listar; use '.' para a atual"}},
            "required": ["caminho"]}}},
    {"type": "function", "function": {
        "name": "ler",
        "description": "Le um arquivo de texto inteiro dentro da pasta de trabalho.",
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string", "description": "arquivo a ler"}},
            "required": ["caminho"]}}},
    {"type": "function", "function": {
        "name": "buscar",
        "description": ("Procura um texto em todos os arquivos abaixo de um "
                        "caminho (grep recursivo). Use antes de ler arquivo "
                        "grande."),
        "parameters": {"type": "object", "properties": {
            "padrao": {"type": "string", "description": "texto ou regex"},
            "caminho": {"type": "string", "description": "onde procurar"}},
            "required": ["padrao", "caminho"]}}},
    {"type": "function", "function": {
        "name": "escrever",
        "description": ("Grava um arquivo. A pessoa ve o diff e autoriza antes. "
                        "Nao use para apagar: nao ha ferramenta de apagar."),
        "parameters": {"type": "object", "properties": {
            "caminho": {"type": "string"},
            "conteudo": {"type": "string", "description": "conteudo COMPLETO do arquivo"}},
            "required": ["caminho", "conteudo"]}}},
    {"type": "function", "function": {
        "name": "executar",
        "description": ("Roda um programa na pasta de trabalho e devolve a "
                        "saida. Sem shell: nada de pipes, redirecionamento ou "
                        "encadeamento. A pessoa autoriza cada comando."),
        "parameters": {"type": "object", "properties": {
            "comando": {"type": "string",
                        "description": "programa e argumentos, ex: 'ls -la docs'"}},
            "required": ["comando"]}}},
]


def executa(ctx: Contexto, nome: str, args: dict) -> tuple[str, bool]:
    """(resultado_para_o_modelo, deu_certo).

    Nome fora do catalogo nao vira acao (ADR 0035) — vira resposta dizendo
    isso, para o modelo se corrigir em vez de insistir.
    """
    if nome not in ACOES:
        return (f"nao existe ferramenta chamada {nome!r}. As que existem sao: "
                f"{', '.join(sorted(ACOES))}."), False
    fn, sempre_confirma = ACOES[nome]
    if not sempre_confirma and not ctx.auto_leitura:
        resumo = ", ".join(f"{k}={v!r}" for k, v in args.items())
        r = _pergunta(f"{nome}({resumo})", f"somente leitura, em {ctx.raiz}")
        if r == "sem_terminal":
            return (f"{SEM_TERMINAL} Para leitura sem confirmação, abra com "
                    f"`jared -f leitura` ou use /ferramentas leitura."), False
        if r != "sim":
            return "a pessoa recusou esta leitura", False
    try:
        return fn(ctx, args), True
    except Recusa as e:
        return f"recusado: {e}", False
    except Exception as e:                      # nunca derruba o REPL
        return f"a ferramenta falhou: {type(e).__name__}: {e}", False
