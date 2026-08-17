"""A abertura — quatro direções, para escolher uma.

São quatro ESTRUTURAS diferentes, não uma estrutura em quatro cores. A
distinção não é preciosismo: está registrada na sessão 17k do projeto design,
depois de quatro reprovações seguidas — *"variar posição ≠ renovar"*.

  selo      cerimonial e simétrico; a moldura É o sigilo
  espinha   sem moldura; um tentáculo desce a calha e o texto pende dele
  dossie    ficha de caso; dados tabulados, nada de figura
  silhueta  a figura encapuzada em blocos, estado empilhado ao lado

Restrição técnica que virou restrição de desenho: só entram caracteres de
largura 1 garantida — ASCII, desenho de caixa (U+2500–257F) e blocos
(U+2580–259F). Glifo de largura ambígua desalinha a moldura em metade dos
terminais, e moldura torta destrói tudo.
"""

from __future__ import annotations

import re

from . import tela

_ANSI = re.compile(r"\033\[[0-9;]*m")


def _vis(s: str) -> int:
    """Largura visível, ignorando os códigos de cor."""
    return len(_ANSI.sub("", s))


# --------------------------------------------------------------- paletas --
# Uma por referência. O acento é único e escasso, de propósito.
PALETAS = {
    "carmim":  {"acento": "\033[38;5;131m", "brilho": "\033[38;5;174m",
                "osso": "\033[38;5;223m"},
    "ouro":    {"acento": "\033[38;5;136m", "brilho": "\033[38;5;179m",
                "osso": "\033[38;5;250m"},
    "bruma":   {"acento": "\033[38;5;245m", "brilho": "\033[38;5;252m",
                "osso": "\033[38;5;250m"},
}


def _cores(paleta: str):
    p = PALETAS.get(paleta, PALETAS["carmim"])
    if not tela._COR:
        return {k: "" for k in p} | {"reset": "", "fraco": "", "negrito": ""}
    return {**p, "reset": tela.RESET, "fraco": tela.FRACO, "negrito": tela.NEGRITO}


# ------------------------------------------------------------ A — o selo --

def selo(d: dict, paleta: str = "carmim") -> str:
    c = _cores(paleta)
    a, b, o, r, f = c["acento"], c["brilho"], c["osso"], c["reset"], c["fraco"]
    arte = [
        r"        ╱▀╲        ",
        r"    ╭───┘ └───╮    ",
        r"   ╱ ╲   │   ╱ ╲   ",
        r"  │   ╳──█──╳   │  ",
        r"   ╲ ╱   │   ╲ ╱   ",
        r"    ╰───┐ ┌───╯    ",
        r"        ╲▄╱        ",
    ]
    linhas = [""]
    for i, l in enumerate(arte):
        cor = b if i == 3 else a
        linhas.append(f"      {cor}{l}{r}")
    nome = d["nome"].upper()
    espacado = " ".join(nome)
    linhas.append("")
    linhas.append(f"      {o}{espacado.center(19)}{r}")
    linhas.append(f"      {f}{'─' * 19}{r}")
    linhas.append("")
    linhas.append(f"      {f}{d['motor']}{r}")
    linhas.append(f"      {f}{d['estado']}{r}")
    linhas.append("")
    return "\n".join(linhas)


# -------------------------------------------------------- B — a espinha --

def espinha(d: dict, paleta: str = "ouro") -> str:
    c = _cores(paleta)
    a, b, o, r, f, n = (c["acento"], c["brilho"], c["osso"],
                        c["reset"], c["fraco"], c["negrito"])
    calha = [
        r"  ╭─╮   ",
        r" ╭╯ ╰╮  ",
        r" ╰╮  ╰╮ ",
        r"  ╰╮  │ ",
        r"   │ ╭╯ ",
        r"  ╭╯ │  ",
        r"  ╰─╮╰╮ ",
        r"    ╰─╯ ",
    ]
    texto = [
        f"{n}{d['nome']}{r}",
        f"{f}{'─' * (len(d['nome']) + 4)}{r}",
        "",
        f"{o}{d['motor']}{r}",
        f"{f}{d['estado']}{r}",
        "",
        f"{f}{d['dica']}{r}",
        "",
    ]
    linhas = [""]
    for i, l in enumerate(calha):
        cor = b if i in (0, 7) else a
        direita = texto[i] if i < len(texto) else ""
        linhas.append(f"  {cor}{l}{r}  {direita}")
    linhas.append("")
    return "\n".join(linhas)


# --------------------------------------------------------- C — o dossiê --

def dossie(d: dict, paleta: str = "bruma") -> str:
    c = _cores(paleta)
    a, o, r, f, n = c["acento"], c["osso"], c["reset"], c["fraco"], c["negrito"]
    # W = largura INTERNA. Toda linha vale W entre as duas bordas — a versao
    # anterior calculava tres larguras diferentes e a moldura saiu torta.
    W = 52
    titulo = " DOSSIÊ "
    campos = [
        ("SUJEITO", d["nome"]),
        ("MOTOR", d["motor"]),
        ("CONTEXTO", d["contexto"]),
        ("FERRAMENTAS", d["ferramentas"]),
        ("SETOR", d["setor"]),
    ]
    topo = (f"  {f}┌─{r}{a}{n}{titulo}{r}"
            f"{f}{'─' * (W - 1 - len(titulo))}┐{r}")
    linhas = ["", topo]
    for rotulo, valor in campos:
        pontos = "." * max(2, 16 - len(rotulo))
        corpo = f" {f}{rotulo} {pontos}{r} {o}{valor}{r}"
        preenche = max(0, W - _vis(corpo))
        linhas.append(f"  {f}│{r}{corpo}{' ' * preenche}{f}│{r}")
    linhas.append(f"  {f}└{'─' * W}┘{r}")
    linhas.append(f"  {f}{d['dica']}{r}")
    linhas.append("")
    return "\n".join(linhas)


# ------------------------------------------------------- D — a silhueta --

def silhueta(d: dict, paleta: str = "bruma") -> str:
    c = _cores(paleta)
    a, b, o, r, f, n = (c["acento"], c["brilho"], c["osso"],
                        c["reset"], c["fraco"], c["negrito"])
    figura = [
        (r"    ▄▄▄▄▄    ", a),
        (r"  ▄█▀▀▀▀▀█▄  ", a),
        (r"  █▌  █  ▐█  ", b),
        (r"  ▐█▄▄▄▄▄█▌  ", a),
        (r"   ▓▓▓▓▓▓▓   ", a),
        (r"  ▒▒░▒▒▒░▒▒  ", f),
        (r" ╱ ╰╮ ╱ ╭╯ ╲ ", f),
        (r"╰╮  ╰╯ ╰╯  ╭╯", f),
    ]
    texto = [
        "",
        f"{n}{d['nome']}{r}",
        f"{f}{'─' * (len(d['nome']) + 4)}{r}",
        "",
        f"{o}{d['motor']}{r}",
        f"{f}{d['estado']}{r}",
        "",
        f"{f}{d['dica']}{r}",
    ]
    linhas = [""]
    for i, (l, cor) in enumerate(figura):
        direita = texto[i] if i < len(texto) else ""
        linhas.append(f"  {cor}{l}{r}   {direita}")
    linhas.append("")
    return "\n".join(linhas)


# ------------------------------------------------------- E — o mascote --

DIR_RENDER = __import__("pathlib").Path(__file__).resolve().parent.parent / "arte" / "render"


def suporta_sixel() -> bool:
    """Konsole 24+, foot, mlterm e wezterm falam sixel.

    Detecção por ambiente, não por consulta ao terminal: consultar exige
    escrever uma sequência de controle e ler a resposta com timeout, e um
    terminal que não responde deixaria o arranque pendurado.
    """
    import os
    if os.environ.get("JARED_SIXEL") == "0":
        return False
    if os.environ.get("JARED_SIXEL") == "1":
        return True
    if os.environ.get("KONSOLE_VERSION"):
        return True
    termo = os.environ.get("TERM", "")
    return any(t in termo for t in ("foot", "mlterm", "yaft", "wezterm", "sixel"))


def mascote(d: dict, paleta: str = "bruma") -> str:
    """A figura desenhada com as CÉLULAS do terminal.

    Sixel foi abandonado aqui, e a razão está em dois prints: sixel é imagem
    colada — o terminal reserva um retângulo e o Konsole o preenche com o
    registro de cor 0, então a caixa aparece por mais que se acerte a cor.

    O `.celulas` é texto: onde a arte é transparente, nenhuma cor de fundo é
    emitida, e o fundo REAL do terminal aparece. Sem retângulo, e sobrevive a
    troca de tema sem regerar nada.
    """
    c = _cores(paleta)
    o, r, f, n = c["osso"], c["reset"], c["fraco"], c["negrito"]
    nome_arte = d.get("arte", "ritual")

    p = DIR_RENDER / f"{nome_arte}.celulas"
    if not p.exists():
        return dossie(d, paleta)          # sem arte desenhada, cai no dossiê

    arte = p.read_text(encoding="utf-8", errors="replace")
    estado = (f"\n  {n}{d['nome']}{r}  {f}·{r}  {o}{d['motor']}{r}\n"
              f"  {f}{d['estado']}{r}\n"
              f"  {f}{d['dica']}{r}\n")
    return "\n" + arte + "\n" + estado


DIRECOES = {
    "mascote": (mascote, "bruma", "a pixel art gerada (sixel, ou meio-bloco)"),
    "selo": (selo, "carmim", "cerimonial e simétrico; a moldura é o sigilo"),
    "espinha": (espinha, "ouro", "sem moldura; o texto pende de um tentáculo"),
    "dossie": (dossie, "bruma", "ficha de caso; dados tabulados, sem figura"),
    "silhueta": (silhueta, "bruma", "a figura encapuzada, estado ao lado"),
    "nenhuma": (None, "", "só uma linha de estado, como está hoje"),
}


def desenha(nome: str, dados: dict, paleta: str = "") -> str:
    entrada = DIRECOES.get(nome)
    if not entrada or entrada[0] is None:
        return ""
    fn, padrao, _ = entrada
    return fn(dados, paleta or padrao)


def demonstra(dados: dict) -> None:
    """Mostra as quatro, com o nome de cada uma, para escolher."""
    for nome, (fn, padrao, descricao) in DIRECOES.items():
        if fn is None:
            continue
        print(f"\n{tela.FRACO}{'═' * 58}{tela.RESET}")
        print(f"{tela.NEGRITO}  {nome}{tela.RESET}"
              f"{tela.FRACO}  ·  {descricao}{tela.RESET}")
        print(f"{tela.FRACO}{'═' * 58}{tela.RESET}")
        print(fn(dados, padrao))
    print(f"{tela.FRACO}{'═' * 58}{tela.RESET}")
    print(f"  escolha com {tela.ACENTO}/abertura <nome>{tela.RESET}"
          f"{tela.FRACO}  ·  paletas: carmim, ouro, bruma{tela.RESET}\n")
