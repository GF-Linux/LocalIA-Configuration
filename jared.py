#!/usr/bin/env python3
"""jared — conversa com um modelo de linguagem no terminal.

Desenho em uma frase: o modelo propoe, voce aciona.

  jared                    abre na pasta atual
  jared -m qwen-think      abre com outro perfil de modelo
  jared "pergunta"         responde e sai (serve para pipe e script)
  jared --modelos          lista o registro e sai

Dentro, `/ajuda` mostra os comandos.
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import readline
import subprocess
import sys
import re
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nucleo import (abertura, acervo, config, ferramentas, perfil,  # noqa: E402
                    provedores, skills, tela)

MAX_VOLTAS_FERRAMENTA = 8
ARQ_HISTORICO = config.DIR_CONFIG / "historico"

# O prompt de sistema NAO mora aqui. Mora em ~/.config/jared/perfil.md, escrito
# pelo dono. Ver nucleo/perfil.py para o porque.

SISTEMA_FERRAMENTAS = """
Voce tem ferramentas para olhar e agir na pasta de trabalho. Regras:

- prefira `buscar` antes de `ler` quando o arquivo pode ser grande;
- so proponha uma acao quando ela for necessaria para responder;
- cada acao que escreve ou executa e autorizada pela pessoa antes de rodar;
  se ela recusar, aceite e siga sem insistir;
- nao existe ferramenta para apagar arquivo. Nao proponha apagar nada;
- nao invente nome de ferramenta: use so as que estao declaradas.
"""


# --------------------------------------------------------------- estado --

class Sessao:
    def __init__(self, cfg: config.Config, apelido: str, raiz: Path):
        self.cfg = cfg
        self.apelido = apelido
        self.mod = cfg.modelos[apelido]
        self.think = self.mod.think
        self.usa_ferramentas = False
        self.ctx_ferr = ferramentas.Contexto(raiz=raiz,
                                             max_linhas=cfg.max_linhas_saida)
        self.mensagens: list[dict] = []
        self.skills_ativas: dict[str, skills.Skill] = {}
        self.projeto_ativo: str = ""
        self.contexto_extra: list[tuple[str, str]] = []   # (rotulo, texto)
        self.idx_skills = skills.indice()
        self.ult_tok_prompt = 0
        self._ultima_busca_ref = None       # (acervo, [verbetes]) da última /ref
        self._refs_carregados: set = set()  # caminhos já no contexto

    # -- prompt de sistema montado na hora, para refletir o estado atual --
    def sistema(self) -> str:
        partes = [perfil.carrega()]
        if self.usa_ferramentas:
            partes.append(SISTEMA_FERRAMENTAS)
            partes.append(f"\nA pasta de trabalho e: {self.ctx_ferr.raiz}")
        for rotulo, txt in self.contexto_extra:
            partes.append(f"\n\n===== {rotulo} =====\n{txt}")
        return "".join(partes)

    def para_envio(self) -> list[dict]:
        return [{"role": "system", "content": self.sistema()}] + self.mensagens

    def tokens_contexto(self) -> int:
        """Estimativa por caracteres — 3,246 chars/token, medido no qwen3.8."""
        n = len(self.sistema())
        for m in self.mensagens:
            n += len(str(m.get("content") or ""))
        return int(n / 3.246)


# ------------------------------------------------------------- desenho --

def escreve_resposta(sess: Sessao, prov) -> tuple[str, list, str]:
    """Renderiza o fluxo. Devolve (texto, chamadas, erro)."""
    tela.marca_modelo(sess.apelido)
    buf: list[str] = []
    chamadas: list = []
    erro = ""
    em_pensamento = False
    t0 = time.time()
    primeiro = None
    tok_saida = 0

    try:
        ferr = ferramentas.ESQUEMAS if sess.usa_ferramentas else None
        for p in prov.conversa(sess.para_envio(), ferr, sess.think):
            if p.erro:
                erro = p.erro
                break
            if p.pensamento:
                if not em_pensamento:
                    print(f"\n{tela.FRACO}  pensando…{tela.RESET}\n  ", end="")
                    tela.abre_pensamento()
                    em_pensamento = True
                print(p.pensamento.replace("\n", "\n  "), end="", flush=True)
            if p.texto:
                if em_pensamento:
                    tela.fecha_pensamento()
                    print("\n")
                    em_pensamento = False
                if primeiro is None:
                    primeiro = time.time() - t0
                buf.append(p.texto)
                print(p.texto, end="", flush=True)
            if p.fim:
                chamadas = p.chamadas
                tok_saida = p.tok_saida
                sess.ult_tok_prompt = p.tok_prompt or sess.ult_tok_prompt
                break
    except KeyboardInterrupt:
        print(f"\n{tela.FRACO}  (interrompido){tela.RESET}")
        return "".join(buf), [], ""
    finally:
        if em_pensamento:
            tela.fecha_pensamento()

    if erro:
        print()
        tela.erro(erro)
        return "", [], erro

    decorrido = time.time() - t0
    if buf:
        print()
        if tok_saida:
            taxa = tok_saida / max(decorrido, 1e-9)
            atraso = f"{primeiro:.1f}s até a 1ª palavra · " if primeiro else ""
            tela.fraco(f"  {atraso}{tok_saida} tok · {taxa:.1f} tok/s")
    return "".join(buf), chamadas, ""


def roda_ferramentas(sess: Sessao, chamadas: list) -> None:
    """Executa as chamadas propostas e devolve os resultados ao modelo."""
    for ch in chamadas:
        fn = ch.get("function") or {}
        nome = fn.get("name") or ""
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if not isinstance(args, dict):
            args = {}
        saida, ok = ferramentas.executa(sess.ctx_ferr, nome, args)
        if ok:
            tela.bom(f"{nome} — {len(saida)} caracteres de volta")
        else:
            tela.fraco(f"  {nome}: {saida.splitlines()[0][:70]}")
        sess.mensagens.append({"role": "tool", "content": saida, "name": nome})


# Sinais de que o modelo TENTOU agir sem ter ferramenta: ele narra a ação, ou
# escreve uma chamada de função em bloco de código. Os nomes inventados entram
# de propósito — quando as ferramentas estão desligadas ele não conhece os nomes
# de verdade e chuta em inglês.
_TENTOU_AGIR = re.compile(
    r"\b(vou|irei|deixe-me|posso)\s+(ler|listar|buscar|executar|rodar|abrir|analisar)\b"
    r"|ferramenta apropriada"
    r"|\b(list_directory|read_file|search_files|run_command|execute)\s*\(",
    re.IGNORECASE,
)


def avisa_ferramentas_desligadas(sess: Sessao, texto: str) -> None:
    """Explica o silêncio quando o modelo promete agir e nada acontece.

    **Isto existe por causa de um relato de uso.** Pedido para analisar um
    repositório, o modelo respondia "vou listar os arquivos usando a ferramenta
    apropriada" e devolvia o prompt — sem nunca listar nada. Medido contra o
    Ollama: com os esquemas declarados ele emite `tool_calls` certinho; sem eles
    ele narra a ferramenta em texto, porque não sabe que não a tem.

    A conversa continua sendo o padrão (ADR 0003) — o que faltava era a tela
    dizer por que a ação prometida não veio.
    """
    if sess.usa_ferramentas or not texto or not _TENTOU_AGIR.search(texto):
        return
    tela.aviso("ele prometeu uma ação, mas as ferramentas estão desligadas")
    tela.fraco(f"  ligue com {tela.ACENTO}/ferramentas leitura{tela.RESET}"
               f"{tela.FRACO} (ou `on`) e peça de novo")
    tela.fraco(f"  a pasta de trabalho é {sess.ctx_ferr.raiz} — troque com "
               f"{tela.ACENTO}/pasta <caminho>{tela.RESET}")


def uma_volta(sess: Sessao) -> None:
    """Um turno completo, incluindo o laco de ferramentas."""
    prov = provedores.cria(sess.mod)
    for volta in range(MAX_VOLTAS_FERRAMENTA):
        texto, chamadas, erro = escreve_resposta(sess, prov)
        if erro:
            return
        msg: dict = {"role": "assistant", "content": texto}
        if chamadas:
            msg["tool_calls"] = chamadas
        sess.mensagens.append(msg)
        if not chamadas:
            avisa_ferramentas_desligadas(sess, texto)
            return
        roda_ferramentas(sess, chamadas)
    tela.aviso(f"parei depois de {MAX_VOLTAS_FERRAMENTA} rodadas de ferramenta")


# ------------------------------------------------------------ comandos --

def cmd_ajuda(sess: Sessao, arg: str) -> bool:
    print(f"""
{tela.NEGRITO}conversa{tela.RESET}
  {tela.ACENTO}/think{tela.RESET} [on|off]      liga o raciocinio. Custa minutos por resposta.
  {tela.ACENTO}/limpar{tela.RESET}              esquece a conversa (mantem skills e projeto)
  {tela.ACENTO}/salvar{tela.RESET} [nome]       grava a conversa em ~/.config/jared/sessoes

{tela.NEGRITO}modelo{tela.RESET}
  {tela.ACENTO}/modelos{tela.RESET}             lista o registro
  {tela.ACENTO}/modelo{tela.RESET} <apelido>    troca de modelo no meio da conversa
  {tela.ACENTO}/config{tela.RESET}              abre modelos.toml no editor
  {tela.ACENTO}/recarregar{tela.RESET}          rele o modelos.toml sem sair

{tela.NEGRITO}contexto{tela.RESET}
  {tela.ACENTO}/skills{tela.RESET} [busca]      procura entre as skills instaladas
  {tela.ACENTO}/skill{tela.RESET} <nome>        carrega o corpo de uma skill
  {tela.ACENTO}/projetos{tela.RESET}            lista os projetos do segundo cerebro
  {tela.ACENTO}/projeto{tela.RESET} <nome>      carrega overview + status + 2 ultimas sessoes
  {tela.ACENTO}/ref{tela.RESET} [acervo] <busca> procura num acervo de referência (h4cker...)
  {tela.ACENTO}/ref+{tela.RESET} <n>            carrega o resultado nº n da última busca
  {tela.ACENTO}/descarregar{tela.RESET} [nome]  tira uma skill/projeto do contexto (sem nome: tudo)
  {tela.ACENTO}/ctx{tela.RESET}                 quanto do contexto esta ocupado

{tela.NEGRITO}acao{tela.RESET}
  {tela.ACENTO}/ferramentas{tela.RESET} [on|off|leitura]
        on       o modelo pode propor ler, buscar, escrever e executar
        leitura  ler/buscar/listar deixam de pedir confirmacao
        off      volta a ser so conversa
  {tela.ACENTO}/pasta{tela.RESET} [caminho]     muda a pasta de trabalho (raiz do confinamento)

{tela.NEGRITO}identidade{tela.RESET}
  {tela.ACENTO}/perfil{tela.RESET} [ver|padrao]  quem o assistente é — abre ~/.config/jared/perfil.md
  {tela.ACENTO}/abertura{tela.RESET} [nome] [paleta]
        sem argumento mostra as direções; nomes: selo, espinha, dossie,
        silhueta, nenhuma · paletas: carmim, ouro, bruma

{tela.NEGRITO}terminal{tela.RESET}
  {tela.ACENTO}!{tela.RESET}<comando>           roda um comando SEU, sem passar pelo modelo
  {tela.ACENTO}/sair{tela.RESET}                ou Ctrl-D
""")
    return True


def cmd_modelos(sess: Sessao, arg: str) -> bool:
    print()
    for ap, m in sess.cfg.modelos.items():
        marca = f"{tela.ACENTO}●{tela.RESET}" if ap == sess.apelido else " "
        ok, motivo = m.pronto
        onde = f"{tela.PERIGO}remoto{tela.RESET}" if m.remoto else f"{tela.CINZA}local{tela.RESET}"
        estado = "" if ok else f"  {tela.PERIGO}({motivo}){tela.RESET}"
        print(f" {marca} {tela.NEGRITO}{ap:<14}{tela.RESET} {m.modelo:<18} {onde} "
              f"{tela.CINZA}ctx {m.n_ctx//1024}k{tela.RESET}{estado}")
        if m.notas:
            print(f"   {tela.FRACO}{m.notas}{tela.RESET}")
    print()
    return True


def cmd_modelo(sess: Sessao, arg: str) -> bool:
    if not arg:
        return cmd_modelos(sess, "")
    if arg not in sess.cfg.modelos:
        tela.erro(f"nao ha modelo {arg!r}. Veja /modelos.")
        return True
    novo = sess.cfg.modelos[arg]
    ok, motivo = novo.pronto
    if not ok:
        tela.erro(f"{arg} nao esta usavel: {motivo}")
        return True
    prov = provedores.cria(novo)
    disp, motivo = prov.disponivel()
    if not disp:
        tela.erro(motivo)
        return True
    sess.apelido, sess.mod, sess.think = arg, novo, novo.think
    tela.bom(f"agora falando com {arg} ({novo.modelo})")
    if novo.remoto:
        tela.aviso("modelo REMOTO: daqui em diante o texto sai da máquina.")
    return True


def cmd_think(sess: Sessao, arg: str) -> bool:
    a = arg.strip().lower()
    if a in ("on", "sim", "1", "ligar", ""):
        sess.think = True
        tela.bom("raciocínio ligado — respostas difíceis podem levar minutos")
    elif a in ("off", "nao", "não", "0", "desligar"):
        sess.think = False
        tela.bom("raciocínio desligado")
    else:
        tela.erro("use /think on ou /think off")
    return True


def cmd_ferramentas(sess: Sessao, arg: str) -> bool:
    a = arg.strip().lower()
    if a in ("on", "sim", "ligar", ""):
        sess.usa_ferramentas = True
        sess.ctx_ferr.auto_leitura = False
        tela.bom(f"ferramentas ligadas, confinadas a {sess.ctx_ferr.raiz}")
        tela.fraco("  toda ação é proposta; quem aciona é você")
    elif a in ("leitura", "auto", "auto-leitura"):
        sess.usa_ferramentas = True
        sess.ctx_ferr.auto_leitura = True
        tela.bom("ferramentas ligadas; ler/buscar/listar não perguntam mais")
        tela.fraco("  escrever e executar continuam pedindo confirmação")
    elif a in ("off", "nao", "não", "desligar"):
        sess.usa_ferramentas = False
        tela.bom("ferramentas desligadas — só conversa")
    else:
        tela.erro("use /ferramentas on | leitura | off")
    return True


def cmd_pasta(sess: Sessao, arg: str) -> bool:
    if not arg:
        print(f"  {sess.ctx_ferr.raiz}")
        return True
    novo = Path(os.path.expanduser(arg)).resolve()
    if not novo.is_dir():
        tela.erro(f"não é uma pasta: {novo}")
        return True
    sess.ctx_ferr.raiz = novo
    tela.bom(f"pasta de trabalho: {novo}")
    return True


def cmd_skills(sess: Sessao, arg: str) -> bool:
    achadas = skills.procura(sess.idx_skills, arg.strip())
    if not achadas:
        tela.fraco(f"  nenhuma skill casa com {arg!r} (de {len(sess.idx_skills)})")
        return True
    print()
    for s in achadas[:25]:
        marca = f"{tela.ACENTO}●{tela.RESET}" if s.nome in sess.skills_ativas else " "
        d = s.descricao[:88] + ("…" if len(s.descricao) > 88 else "")
        print(f" {marca} {tela.NEGRITO}{s.nome}{tela.RESET}")
        if d:
            print(f"   {tela.FRACO}{d}{tela.RESET}")
    if len(achadas) > 25:
        tela.fraco(f"  … e mais {len(achadas)-25}. Refine a busca.")
    print()
    return True


def cmd_skill(sess: Sessao, arg: str) -> bool:
    nome = arg.strip()
    if not nome:
        tela.erro("qual skill? Use /skills para procurar.")
        return True
    achadas = skills.procura(sess.idx_skills, nome)
    if not achadas:
        tela.erro(f"não achei skill {nome!r}")
        return True
    s = achadas[0]
    if s.nome in sess.skills_ativas:
        tela.fraco(f"  {s.nome} já está carregada")
        return True
    corpo = s.corpo()
    sess.skills_ativas[s.nome] = s
    sess.contexto_extra.append((f"SKILL: {s.nome}", corpo))
    tela.bom(f"{s.nome} carregada (~{s.tokens_aprox()} tokens)")
    if len(achadas) > 1:
        tela.fraco(f"  (também casavam: {', '.join(x.nome for x in achadas[1:4])})")
    return True


def cmd_projetos(sess: Sessao, arg: str) -> bool:
    ps = skills.projetos(sess.cfg.segundo_cerebro)
    if not ps:
        tela.erro(f"não achei projetos em {sess.cfg.segundo_cerebro!r}/projetos")
        return True
    print()
    for nome in ps:
        marca = f"{tela.ACENTO}●{tela.RESET}" if nome == sess.projeto_ativo else " "
        print(f" {marca} {nome}")
    print()
    return True


def cmd_projeto(sess: Sessao, arg: str) -> bool:
    nome = arg.strip()
    if not nome:
        return cmd_projetos(sess, "")
    ps = skills.projetos(sess.cfg.segundo_cerebro)
    if nome not in ps:
        perto = [n for n in ps if nome in n]
        if len(perto) == 1:
            nome = perto[0]
        else:
            tela.erro(f"não achei projeto {nome!r}. Veja /projetos.")
            return True
    txt = ps[nome].contexto()
    if not txt:
        tela.erro(f"{nome} não tem _overview/status/sessões para carregar")
        return True
    sess.contexto_extra = [(r, t) for r, t in sess.contexto_extra
                           if not r.startswith("PROJETO:")]
    sess.contexto_extra.append((f"PROJETO: {nome}", txt))
    sess.projeto_ativo = nome
    tela.bom(f"contexto de {nome} carregado (~{int(len(txt)/3.246)} tokens)")
    tela.fraco("  overview + status + 2 sessões mais recentes")
    return True


def cmd_descarregar(sess: Sessao, arg: str) -> bool:
    a = arg.strip()
    if not a:
        sess.contexto_extra.clear()
        sess.skills_ativas.clear()
        sess.projeto_ativo = ""
        sess._refs_carregados.clear()
        tela.bom("contexto extra limpo")
        return True
    antes = len(sess.contexto_extra)
    sess.contexto_extra = [(r, t) for r, t in sess.contexto_extra
                           if a.lower() not in r.lower()]
    sess.skills_ativas.pop(a, None)
    if sess.projeto_ativo and a.lower() in sess.projeto_ativo.lower():
        sess.projeto_ativo = ""
    if len(sess.contexto_extra) == antes:
        tela.erro(f"nada carregado casa com {a!r}")
    else:
        tela.bom(f"descarregado: {a}")
    return True


def cmd_ctx(sess: Sessao, arg: str) -> bool:
    est = sess.tokens_contexto()
    teto = sess.mod.n_ctx
    pct = 100 * est / teto if teto else 0
    barra_n = int(min(pct, 100) / 100 * 34)
    cor = tela.PERIGO if pct > 85 else (tela.ACENTO if pct > 60 else tela.OK)
    print(f"\n  {cor}{'█'*barra_n}{tela.FRACO}{'░'*(34-barra_n)}{tela.RESET} "
          f"{pct:.0f}%")
    print(f"  {tela.CINZA}~{est} de {teto} tokens estimados{tela.RESET}")
    if sess.ult_tok_prompt:
        print(f"  {tela.CINZA}última chamada real: {sess.ult_tok_prompt} tokens "
              f"de entrada{tela.RESET}")
    n_ref = len(sess._refs_carregados)
    print(f"  {tela.CINZA}{len(sess.mensagens)} mensagens · "
          f"{len(sess.skills_ativas)} skill(s)"
          + (f" · {n_ref} ref(s)" if n_ref else "")
          + (f" · projeto {sess.projeto_ativo}" if sess.projeto_ativo else "")
          + f"{tela.RESET}")
    if pct > 85:
        tela.aviso("perto do teto: /limpar, ou /modelo qwen-longo para 64k")
    print()
    return True


def cmd_limpar(sess: Sessao, arg: str) -> bool:
    n = len(sess.mensagens)
    sess.mensagens.clear()
    tela.bom(f"{n} mensagens esquecidas (skills e projeto continuam)")
    return True


def cmd_salvar(sess: Sessao, arg: str) -> bool:
    nome = (arg.strip() or time.strftime("%Y-%m-%d-%H%M")) + ".md"
    alvo = config.DIR_SESSOES / nome
    linhas = [f"# conversa — {sess.apelido} ({sess.mod.modelo})", ""]
    if sess.projeto_ativo:
        linhas.append(f"projeto: {sess.projeto_ativo}")
    if sess.skills_ativas:
        linhas.append(f"skills: {', '.join(sess.skills_ativas)}")
    linhas.append("")
    for m in sess.mensagens:
        papel = {"user": "você", "assistant": sess.apelido,
                 "tool": "ferramenta"}.get(m["role"], m["role"])
        linhas.append(f"## {papel}\n\n{m.get('content') or ''}\n")
    alvo.write_text("\n".join(linhas), encoding="utf-8")
    tela.bom(f"gravado em {alvo}")
    return True


def cmd_config(sess: Sessao, arg: str) -> bool:
    ed = config.acha_editor()
    subprocess.run([ed, str(config.ARQ_MODELOS)])
    return cmd_recarregar(sess, "")


def cmd_recarregar(sess: Sessao, arg: str) -> bool:
    cfg, aviso = config.carrega()
    if aviso:
        tela.erro(aviso)
        return True
    sess.cfg = cfg
    if sess.apelido in cfg.modelos:
        sess.mod = cfg.modelos[sess.apelido]
    sess.idx_skills = skills.indice()
    tela.bom(f"recarregado: {len(cfg.modelos)} modelos, {len(sess.idx_skills)} skills")
    return True


def cmd_ref(sess: Sessao, arg: str) -> bool:
    """Busca num acervo de referência e carrega o trecho escolhido.

    /ref                      lista os acervos
    /ref <busca>              procura no acervo ativo (ou único)
    /ref <acervo> <busca>     procura num acervo específico
    /ref+ <n>                 carrega o resultado nº n da última busca
    /ref reindexar [acervo]   regenera o índice
    """
    partes = arg.split()
    disponiveis = config.prefs()  # só para não reclamar de import não usado
    del disponiveis

    if not sess.cfg.acervos:
        tela.erro("nenhum acervo declarado. Adicione [acervos] no modelos.toml "
                  "(/config).")
        return True

    if partes and partes[0] == "reindexar":
        from nucleo import indexar
        alvo = partes[1:] or list(sess.cfg.acervos)
        for nome in alvo:
            raiz = sess.cfg.acervos.get(nome)
            if not raiz:
                tela.erro(f"acervo {nome!r} não existe"); continue
            ac = acervo.indexa(nome, raiz,
                                com_pdf=nome in sess.cfg.acervos_pdf)
            acervo.grava(ac)
            tela.bom(f"{nome}: {len(ac.verbetes)} verbetes reindexados")
        return True

    if not partes:
        print()
        for nome, raiz in sess.cfg.acervos.items():
            ac = acervo.carrega(nome)
            n = len(ac.verbetes) if ac else 0
            estado = f"{n} verbetes" if ac else "não indexado (/ref reindexar)"
            print(f"  {tela.NEGRITO}{nome}{tela.RESET}  {tela.FRACO}{estado} · "
                  f"{raiz}{tela.RESET}")
        tela.fraco("  /ref <busca>  ·  /ref+ <n> para carregar um resultado")
        print()
        return True

    # acervo explícito se o 1º token casar com um nome
    if partes[0] in sess.cfg.acervos:
        nome_ac, busca = partes[0], " ".join(partes[1:])
    else:
        nome_ac, busca = next(iter(sess.cfg.acervos)), arg

    ac = acervo.carrega(nome_ac)
    if not ac:
        tela.erro(f"{nome_ac} não está indexado. Rode /ref reindexar {nome_ac}.")
        return True
    achados = ac.procura(busca, 12)
    if not achados:
        tela.fraco(f"  nada em {nome_ac} casa com {busca!r}")
        return True
    sess._ultima_busca_ref = (nome_ac, achados)
    print()
    for i, v in enumerate(achados, 1):
        marca = "●" if v.caminho in sess._refs_carregados else " "
        print(f"  {tela.ACENTO}{i:>2}{tela.RESET} {marca} "
              f"{tela.NEGRITO}{v.titulo[:52]}{tela.RESET}")
        cauda = f"~{v.tokens_aprox()} tok"
        print(f"       {tela.FRACO}{v.dominio[:56]}  ·  {cauda}{tela.RESET}")
    tela.fraco(f"  /ref+ <n> carrega no contexto  ·  {len(achados)} resultado(s)")
    print()
    return True


def cmd_ref_mais(sess: Sessao, arg: str) -> bool:
    """Carrega no contexto um resultado da última /ref."""
    if not getattr(sess, "_ultima_busca_ref", None):
        tela.erro("faça uma /ref <busca> antes")
        return True
    nome_ac, achados = sess._ultima_busca_ref
    try:
        n = int(arg.strip())
        v = achados[n - 1]
    except (ValueError, IndexError):
        tela.erro(f"use /ref+ <n>, de 1 a {len(achados)}")
        return True
    if v.caminho in sess._refs_carregados:
        tela.fraco(f"  {v.titulo} já está no contexto")
        return True
    corpo = v.corpo()
    sess._refs_carregados.add(v.caminho)
    sess.contexto_extra.append((f"REFERÊNCIA [{nome_ac}]: {v.titulo}", corpo))
    tela.bom(f"{v.titulo} carregada (~{v.tokens_aprox()} tokens)")
    return True


def cmd_perfil(sess: Sessao, arg: str) -> bool:
    """O perfil é quem o assistente é. Mora em arquivo, não em código."""
    a = arg.strip().lower()
    if a in ("ver", "mostrar"):
        print()
        print(tela.corta(perfil.carrega(), 60))
        print()
        return True
    if a in ("padrao", "padrão", "restaurar"):
        p = perfil.restaura_semente()
        tela.bom(f"perfil restaurado ({p}); o anterior virou perfil.md.anterior")
        return True
    subprocess.run([config.acha_editor(), str(perfil.garante())])
    tela.bom("perfil atualizado — vale a partir da próxima mensagem")
    return True


def cmd_abertura(sess: Sessao, arg: str) -> bool:
    partes = arg.split()
    nome = partes[0].lower() if partes else ""
    paleta = partes[1].lower() if len(partes) > 1 else ""
    arte = partes[2].lower() if len(partes) > 2 else ""
    if not nome:
        abertura.demonstra(dados_abertura(sess))
        return True
    if nome not in abertura.DIRECOES:
        tela.erro(f"não conheço a abertura {nome!r}. "
                  f"Há: {', '.join(abertura.DIRECOES)}")
        return True
    if paleta and paleta not in abertura.PALETAS:
        tela.erro(f"paleta {paleta!r} não existe. "
                  f"Há: {', '.join(abertura.PALETAS)}")
        return True
    p = config.prefs()
    p["abertura"], p["paleta"] = nome, paleta
    if arte:
        p["arte"] = arte
    config.grava_prefs(p)
    tela.bom(f"abertura: {nome}" + (f" · paleta {paleta}" if paleta else ""))
    if nome != "nenhuma":
        print(abertura.desenha(nome, dados_abertura(sess), paleta))
    return True


def cmd_sair(sess: Sessao, arg: str) -> bool:
    return False


def dados_abertura(sess: Sessao) -> dict:
    """Os campos que toda direção de abertura consome."""
    onde = "remoto" if sess.mod.remoto else "local"
    casa = str(Path.home())
    setor = str(sess.ctx_ferr.raiz).replace(casa, "~")
    if len(setor) > 34:
        setor = "…" + setor[-33:]
    estado = f"ctx {sess.mod.n_ctx // 1024}k"
    estado += " · think" if sess.think else ""
    estado += " · ferramentas" if sess.usa_ferramentas else ""
    return {
        "nome": "jared",
        "motor": f"{sess.mod.modelo} · {onde}",
        "estado": estado,
        "contexto": f"{sess.mod.n_ctx:,} tokens".replace(",", " "),
        "ferramentas": "ativas" if sess.usa_ferramentas else "inativas",
        "setor": setor,
        "dica": "/ajuda para os comandos · Ctrl-D para sair",
        "arte": config.prefs().get("arte", "ritual"),
    }


COMANDOS = {
    "ajuda": cmd_ajuda, "help": cmd_ajuda, "?": cmd_ajuda,
    "perfil": cmd_perfil, "abertura": cmd_abertura,
    "ref": cmd_ref, "ref+": cmd_ref_mais, "referencia": cmd_ref,
    "modelos": cmd_modelos, "modelo": cmd_modelo,
    "think": cmd_think, "raciocinio": cmd_think,
    "ferramentas": cmd_ferramentas, "pasta": cmd_pasta,
    "skills": cmd_skills, "skill": cmd_skill,
    "projetos": cmd_projetos, "projeto": cmd_projeto,
    "descarregar": cmd_descarregar,
    "ctx": cmd_ctx, "contexto": cmd_ctx,
    "limpar": cmd_limpar, "salvar": cmd_salvar,
    "config": cmd_config, "recarregar": cmd_recarregar,
    "sair": cmd_sair, "quit": cmd_sair, "exit": cmd_sair,
}

#? O QUE CADA COMANDO FAZ — Decisão sobre a lista do Tab 17/08/2026
#!
#! 1. O `COMANDOS` acima tem APELIDOS: `ajuda`/`help`/`?` são o mesmo comando, e
#!    `sair`/`quit`/`exit` também. O completador listava as chaves cruas, então a
#!    pessoa via o mesmo comando três vezes, sem saber que era o mesmo.
#! 2. Esta tabela tem só o nome CANÔNICO, e uma linha dizendo o que ele faz.
#! 3. Digitar o apelido continua funcionando — ele só não é mais oferecido.
#! 4. Ordem de assunto, não alfabética: é a ordem em que se precisa deles.
DESCRICAO = {
    "ajuda":        "mostra esta lista",
    "think":        "liga o raciocínio; custa minutos por resposta",
    "limpar":       "esquece a conversa (mantém skills e projeto)",
    "salvar":       "grava a conversa em ~/.config/jared/sessoes",
    "ctx":          "quanto do contexto já está ocupado",
    "modelos":      "lista os modelos do registro",
    "modelo":       "troca de modelo no meio da conversa",
    "config":       "abre o modelos.toml no editor",
    "recarregar":   "relê o modelos.toml sem sair",
    "ferramentas":  "on | leitura | off — deixa o modelo agir na pasta",
    "pasta":        "muda a pasta de trabalho (raiz do confinamento)",
    "skills":       "procura entre as skills instaladas",
    "skill":        "carrega o corpo de uma skill no contexto",
    "projetos":     "lista os projetos do segundo cérebro",
    "projeto":      "carrega overview, status e as 2 últimas sessões",
    "ref":          "procura num acervo de referência (h4cker, livros)",
    "ref+":         "carrega o resultado nº n da última busca",
    "descarregar":  "tira uma skill ou projeto do contexto",
    "perfil":       "quem o assistente é — abre o perfil.md",
    "abertura":     "troca o desenho de abertura",
    "sair":         "encerra (ou Ctrl-D)",
}

#* Os apelidos que existem mas NÃO são oferecidos no Tab, para a lista não
#* repetir o mesmo comando com nomes diferentes.
APELIDOS = {k for k in COMANDOS if k not in DESCRICAO}


def trata_barra(sess: Sessao, linha: str) -> bool:
    """Devolve False para encerrar o programa."""
    corpo = linha[1:].strip()
    nome, _, arg = corpo.partition(" ")

    # `/` sozinho abre o menu. Antes caía em COMANDOS.get("") e respondia
    # "não conheço /" — quem digita a barra está justamente perguntando o que
    # existe, e levava um erro por isso.
    if not nome:
        return cmd_ajuda(sess, "")

    fn = COMANDOS.get(nome.lower())
    if not fn:
        perto = [c for c in COMANDOS if c.startswith(nome.lower())]
        tela.erro(f"não conheço /{nome}"
                  + (f" — você quis dizer /{perto[0]}?" if perto else "")
                  + "   (/ajuda lista tudo)")
        return True
    return fn(sess, arg.strip())


# ---------------------------------------------------------------- main --

def prepara_historico() -> None:
    config.DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    try:
        readline.read_history_file(ARQ_HISTORICO)
    except (OSError, FileNotFoundError):
        pass
    readline.set_history_length(2000)
    atexit.register(lambda: _grava_historico())


def _grava_historico() -> None:
    try:
        readline.write_history_file(ARQ_HISTORICO)
    except OSError:
        pass


def completa(sess: Sessao):
    def fn(texto: str, estado: int):
        buf = readline.get_line_buffer()
        if not buf.startswith("/"):
            return None
        partes = buf[1:].split(" ")
        if len(partes) <= 1:
            #! Só os canônicos: `help` e `?` fazem o mesmo que `ajuda`, e ver o
            #!   mesmo comando três vezes na lista não ajuda ninguém.
            cands = [f"/{c}" for c in DESCRICAO if c.startswith(partes[0])]
        elif partes[0] in ("modelo",):
            cands = [m for m in sess.cfg.modelos if m.startswith(partes[-1])]
        elif partes[0] in ("skill",):
            cands = [s for s in sorted(sess.idx_skills) if s.startswith(partes[-1])][:40]
        elif partes[0] in ("projeto",):
            cands = [p for p in skills.projetos(sess.cfg.segundo_cerebro)
                     if p.startswith(partes[-1])]
        elif partes[0] in ("think", "ferramentas"):
            cands = [x for x in ("on", "off", "leitura") if x.startswith(partes[-1])]
        else:
            return None
        return cands[estado] if estado < len(cands) else None
    return fn


def main() -> int:
    ap = argparse.ArgumentParser(prog="jared", add_help=True,
                                 description="conversa com um modelo no terminal")
    ap.add_argument("pergunta", nargs="*", help="pergunta única (não abre o REPL)")
    ap.add_argument("-m", "--modelo", default="", help="apelido do registro")
    ap.add_argument("-p", "--pasta", default="", help="pasta de trabalho")
    ap.add_argument("--projeto", default="", help="carrega um projeto ao abrir")
    ap.add_argument("--think", action="store_true", help="abre com raciocínio ligado")
    # `-f` sozinho liga pedindo confirmação; `-f leitura` deixa ler/listar/buscar
    # correrem sem perguntar. O segundo existe porque fora do REPL não há quem
    # confirme: sem ele, `jared -f "analise o repo"` num script nunca lê nada.
    ap.add_argument("-f", "--ferramentas", nargs="?", const="on", default="",
                    choices=["on", "leitura"],
                    help="abre com ferramentas ligadas (on|leitura)")
    ap.add_argument("--modelos", action="store_true", help="lista o registro e sai")
    ap.add_argument("--aberturas", action="store_true",
                    help="mostra as direções de abertura e sai")
    a = ap.parse_args()

    cfg, aviso = config.carrega()
    if aviso:
        tela.erro(aviso)
        tela.fraco(f"  edite {config.ARQ_MODELOS}")
        return 1
    perfil.garante()      # semeia ~/.config/jared/perfil.md na 1a execucao

    apelido = a.modelo or cfg.padrao
    if apelido not in cfg.modelos:
        tela.erro(f"não há modelo {apelido!r} no registro. Disponíveis: "
                  f"{', '.join(cfg.modelos)}")
        return 1

    raiz = Path(os.path.expanduser(a.pasta)).resolve() if a.pasta else Path.cwd()
    sess = Sessao(cfg, apelido, raiz)
    if a.think:
        sess.think = True
    if a.ferramentas:
        sess.usa_ferramentas = True
        sess.ctx_ferr.auto_leitura = a.ferramentas == "leitura"

    if a.modelos:
        cmd_modelos(sess, "")
        return 0

    if a.aberturas:
        abertura.demonstra(dados_abertura(sess))
        return 0

    prov = provedores.cria(sess.mod)
    disp, motivo = prov.disponivel()
    if not disp:
        tela.erro(motivo)
        return 1

    if a.projeto:
        cmd_projeto(sess, a.projeto)

    # modo tiro único: serve para pipe e script
    if a.pergunta:
        sess.mensagens.append({"role": "user", "content": " ".join(a.pergunta)})
        uma_volta(sess)
        return 0

    prepara_historico()
    #* O Tab passa a mostrar o que cada comando faz.
    #! O readline, sozinho, imprime só os nomes em colunas. Este gancho troca a
    #!   impressão por uma linha por comando, com a descrição ao lado — que era
    #!   a queixa: a lista dizia os nomes e não explicava nenhum.
    def mostrar(substituicao, candidatos, tamanho):
        print()
        for c in candidatos:
            nome = c.lstrip("/")
            texto = DESCRICAO.get(nome, "")
            print(f"  {tela.ACENTO}/{nome:<13}{tela.RESET}{tela.FRACO}{texto}{tela.RESET}")
        print(f"\n{tela.FRACO}  {len(candidatos)} comandos{tela.RESET}")
        print(tela.prompt() + readline.get_line_buffer(), end="", flush=True)

    readline.set_completion_display_matches_hook(mostrar)
    readline.set_completer(completa(sess))
    readline.parse_and_bind("tab: complete")
    # Um Tab só já mostra as opções. O padrão do readline é completar o prefixo
    # comum no primeiro Tab e só listar no segundo — quem não sabe disso conclui
    # que a completação não existe, que foi exatamente o relato.
    readline.parse_and_bind("set show-all-if-ambiguous on")
    readline.parse_and_bind("set completion-ignore-case on")
    # 136 skills indexadas cabem numa listagem sem a pergunta "mostrar tudo?"
    readline.parse_and_bind("set completion-query-items 200")
    readline.set_completer_delims(" ")

    p = config.prefs()
    arte = abertura.desenha(p.get("abertura", "dossie"), dados_abertura(sess),
                            p.get("paleta", ""))
    if arte:
        print(arte)
    else:
        print()
        tela.cabecalho(sess.apelido, sess.mod, str(sess.ctx_ferr.raiz),
                       sess.usa_ferramentas, sess.think)
        tela.fraco("  /ajuda para os comandos · Ctrl-D para sair")
        print()
    if sess.mod.remoto:
        tela.aviso("modelo REMOTO: o texto sai da máquina.")
        print()

    while True:
        try:
            linha = input(tela.prompt()).strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print(f"\n{tela.FRACO}  (Ctrl-D para sair){tela.RESET}")
            continue
        if not linha:
            continue
        if linha.startswith("!"):
            subprocess.run(linha[1:], shell=True, cwd=str(sess.ctx_ferr.raiz))
            continue
        if linha.startswith("/"):
            if not trata_barra(sess, linha):
                break
            continue
        sess.mensagens.append({"role": "user", "content": linha})
        uma_volta(sess)
        print()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
