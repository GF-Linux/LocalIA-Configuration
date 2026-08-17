"""Configuracao e registro de modelos.

O registro e um TOML editavel a mao: trocar de modelo tem de ser uma linha de
config, nao uma alteracao de codigo. Foi o pedido que originou o programa.
"""

from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_CODIGO = Path(__file__).resolve().parent.parent
DIR_CONFIG = Path(os.environ.get("JARED_CONFIG", Path.home() / ".config" / "jared"))
ARQ_MODELOS = DIR_CONFIG / "modelos.toml"
DIR_SESSOES = DIR_CONFIG / "sessoes"


@dataclass
class Modelo:
    """Uma entrada do registro."""
    apelido: str
    provedor: str                 # "ollama" | "openai-compat"
    modelo: str                   # id real no provedor
    base_url: str = ""
    chave_env: str = ""           # nome da variavel de ambiente com a chave
    n_ctx: int = 16384
    think: bool = False           # padrao de raciocinio para este modelo
    esforco: str = ""             # reasoning_effort, se o provedor aceitar
    temperatura: float = 0.6
    notas: str = ""

    @property
    def remoto(self) -> bool:
        """True quando o texto sai da maquina.

        A tela usa isto para avisar. Nao e detalhe cosmetico: metade das ADRs
        do autor sobre o assistente giram em torno de o dado nao viajar.
        """
        return self.provedor != "ollama"

    @property
    def chave(self) -> str:
        return os.environ.get(self.chave_env, "") if self.chave_env else ""

    @property
    def pronto(self) -> tuple[bool, str]:
        """(usavel, motivo). Modelo remoto sem chave nao e usavel."""
        if self.remoto and not self.chave:
            return False, f"falta a variavel de ambiente {self.chave_env}"
        return True, ""


@dataclass
class Config:
    modelos: dict[str, Modelo] = field(default_factory=dict)
    padrao: str = ""
    # raiz do segundo cerebro, para o comando /projeto
    segundo_cerebro: str = ""
    # acervos de referencia: apelido -> pasta (indexados sob demanda)
    acervos: dict = field(default_factory=dict)
    # quais acervos tambem indexam PDF (catalogo de livros)
    acervos_pdf: set = field(default_factory=set)
    # quantas linhas de saida de ferramenta mostrar antes de cortar
    max_linhas_saida: int = 60

    def modelo(self, apelido: str) -> Modelo | None:
        return self.modelos.get(apelido)


def _semente() -> str:
    """TOML inicial, escrito na primeira execucao."""
    return '''# Registro de modelos do `jared`.
#
# Trocar de modelo e editar este arquivo — nunca o codigo.
# Depois de editar, use /modelo <apelido> ou /recarregar dentro do programa.

padrao = "qwen"
segundo_cerebro = "~/Área de trabalho/segundo-cerebro"

# ---------------------------------------------------------------- local ----
[modelos.qwen]
provedor    = "ollama"
modelo      = "qwen3.8:27b"
n_ctx       = 16384
think       = false
temperatura = 0.6
notas       = "27B hibrido. 12 tok/s nesta maquina; 131k de contexto carrega."

# Mesmo modelo, perfil de contexto longo. Mais camadas na CPU => mais lento.
[modelos.qwen-longo]
provedor    = "ollama"
modelo      = "qwen3.8:27b"
n_ctx       = 65536
think       = false
temperatura = 0.6
notas       = "para ler documento grande; ~8 tok/s"

# Perfil de raciocinio. Custa minutos por resposta — use para problema dificil.
[modelos.qwen-think]
provedor    = "ollama"
modelo      = "qwen3.8:27b"
n_ctx       = 32768
think       = true
temperatura = 0.6
notas       = "18/18 no bloco de coding, mas ~4 min por resposta dificil"

# ------------------------------------------------------------------ api ----
# Preenchido, mas so funciona com a variavel de ambiente definida.
# ATENCAO: modelo remoto = o texto sai da maquina. A tela avisa.
[modelos.deepseek]
provedor  = "openai-compat"
modelo    = "deepseek-v4-flash"
base_url  = "https://api.deepseek.com/v1"
chave_env = "DEEPSEEK_API_KEY"
n_ctx     = 65536
notas     = "o mesmo que move o mascote do EasyContig hoje"
'''


def garante_config() -> Path:
    """Cria ~/.config/jared/modelos.toml na primeira execucao."""
    DIR_CONFIG.mkdir(parents=True, exist_ok=True)
    DIR_SESSOES.mkdir(parents=True, exist_ok=True)
    if not ARQ_MODELOS.exists():
        ARQ_MODELOS.write_text(_semente(), encoding="utf-8")
    return ARQ_MODELOS


def carrega() -> tuple[Config, str]:
    """(config, aviso). Aviso vazio quando tudo certo.

    Nunca levanta por TOML malformado: devolve config vazia + aviso, para o
    programa abrir e dizer o que consertar em vez de morrer no arranque.
    """
    garante_config()
    try:
        with open(ARQ_MODELOS, "rb") as fh:
            cru = tomllib.load(fh)
    except (tomllib.TOMLDecodeError, OSError) as e:
        return Config(), f"nao consegui ler {ARQ_MODELOS}: {e}"

    cfg = Config(
        padrao=cru.get("padrao", ""),
        segundo_cerebro=os.path.expanduser(cru.get("segundo_cerebro", "")),
        acervos={k: os.path.expanduser(v if isinstance(v, str) else v.get("raiz", ""))
                 for k, v in (cru.get("acervos") or {}).items()},
        acervos_pdf={k for k, v in (cru.get("acervos") or {}).items()
                     if isinstance(v, dict) and v.get("pdf")},
        max_linhas_saida=int(cru.get("max_linhas_saida", 60)),
    )
    for apelido, d in (cru.get("modelos") or {}).items():
        if not isinstance(d, dict):
            continue
        cfg.modelos[apelido] = Modelo(
            apelido=apelido,
            provedor=d.get("provedor", "ollama"),
            modelo=d.get("modelo", ""),
            base_url=d.get("base_url", ""),
            chave_env=d.get("chave_env", ""),
            n_ctx=int(d.get("n_ctx", 16384)),
            think=bool(d.get("think", False)),
            esforco=d.get("esforco", ""),
            temperatura=float(d.get("temperatura", 0.6)),
            notas=d.get("notas", ""),
        )
    if not cfg.modelos:
        return cfg, f"{ARQ_MODELOS} nao define nenhum modelo"
    if cfg.padrao not in cfg.modelos:
        cfg.padrao = next(iter(cfg.modelos))
    return cfg, ""


ARQ_PREFS = DIR_CONFIG / "preferencias.json"
PREFS_PADRAO = {"abertura": "dossie", "paleta": ""}


def prefs() -> dict:
    import json
    garante_config()
    if not ARQ_PREFS.exists():
        return dict(PREFS_PADRAO)
    try:
        return {**PREFS_PADRAO, **json.loads(ARQ_PREFS.read_text("utf-8"))}
    except (OSError, ValueError):
        return dict(PREFS_PADRAO)


def grava_prefs(d: dict) -> None:
    import json
    garante_config()
    try:
        ARQ_PREFS.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    except OSError:
        pass


def acha_editor() -> str:
    for var in ("VISUAL", "EDITOR"):
        if os.environ.get(var):
            return os.environ[var]
    for cand in ("nano", "vim", "vi"):
        if shutil.which(cand):
            return cand
    return "nano"
