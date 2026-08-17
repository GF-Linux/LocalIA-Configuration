#!/usr/bin/env python3
"""Gera o mascote em pixel art pela API do Pixel Lab.

Por que existe: a tentativa anterior foi desenhar a figura à mão em blocos
ASCII numa grade de 13 colunas. Não tem resolução para capuz nem para corpo, e
o resultado leu como "um olho gigante sobre uma chaminé" — avaliação do dono, e
justa. Trocar de meio é a correção, não insistir no mesmo com mais capricho.

  python3 arte/gerar.py --saldo
  python3 arte/gerar.py --lote          # gera todas as variantes
  python3 arte/gerar.py --so noturno    # só uma

Chave: variável PIXELLAB_API_KEY, ou ~/.config/jared/pixellab.key (modo 600).
A chave nunca é impressa.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://api.pixellab.ai/v1"
RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"
REFS = Path.home() / "Área de trabalho"
ARQ_CHAVE = Path.home() / ".config" / "jared" / "pixellab.key"

# As três referências que o autor forneceu.
REFERENCIAS = {
    "carmim": REFS / "9ebea47ee0ec8507ebd301ede2520a69.jpg",
    "ouro": REFS / "a854cad78b02567815bd61918bc6678f.jpg",
    "bruma": REFS / "images.jpg",
}

# ---------------------------------------------------------------------------
# TAMANHO: 52x68, que é EXATAMENTE a grade de octantes a 26 colunas x 17 linhas.
#
# Foi o erro de raiz das duas primeiras rodadas: gerar em 132x200 e exibir a
# 52x68 descarta 60% da informação, e nenhuma técnica de terminal recupera
# isso. Pixel art não se reduz — ela nasce na resolução em que vai aparecer.
#
# Junto cai outra premissa: pedir "highly detailed" num sprite de 52 px produz
# ruído, não detalhe. Num sprite pequeno quem carrega a leitura é a SILHUETA e
# o contorno, não a textura.
# ---------------------------------------------------------------------------
# Tamanhos possíveis, todos 1:1 com a grade de octantes (2 x 4 por célula):
#   52 x  68  -> 26 col x 17 lin   (o primeiro lote)
#   64 x  84  -> 32 col x 21 lin
#   78 x 104  -> 39 col x 26 lin
#   96 x 128  -> 48 col x 32 lin
#
# "Menos pixelado" não se resolve com técnica de renderização: o bloco tem
# tamanho fixo (célula/2 x célula/4 = 4,5 x 5 px de tela) e octante já é a
# subdivisão mais fina que existe em caractere. Resolve-se com MAIS BLOCOS
# para a mesma figura — e aí o sombreamento rico, que a 52 px virava ruído,
# passa a valer.

SIGILO = ("small pixel art sprite of a hooded figure in a long dark cloak, "
          "face hidden in deep shadow under the hood, a radiant halo of "
          "spikes behind the head, holding a glowing white sigil orb at the "
          "chest, octopus tentacles curling out on both sides from beneath "
          "the robe, standing, front view, centered, perfectly symmetrical, "
          "strong readable silhouette")

EVITAR = ("blurry, noisy, cluttered, photorealistic, text, watermark, "
          "signature, human legs, giant single eye, chimney, tower, "
          "lighthouse, extra limbs, asymmetric")

VARIANTES = {
    # 64x84 com os tentáculos EXPLÍCITOS na frente da descrição — no lote
    # anterior eles apareciam no fim da frase e sumiram no sprite maior
    "sigilo-tent": dict(
        ref="carmim",
        desc=("small pixel art sprite: large octopus tentacles curling "
              "outward on both sides, and between them a hooded figure in a "
              "dark cloak with a radiant halo of spikes behind the head and a "
              "glowing white sigil orb at the chest, face in deep shadow, "
              "front view, perfectly symmetrical, bone white and charcoal, "
              "smooth shading, strong silhouette"),
        tam=(64, 84), estilo=45, outline="selective outline",
        shading="detailed shading", detail="medium detail"),
    "sigilo-tent2": dict(
        ref="ouro",
        desc=("small pixel art sprite of an eldritch hooded priest, eight "
              "thick octopus tentacles with visible suckers spreading "
              "symmetrically from under a long dark robe, radiant spiked halo "
              "behind the hood, glowing sigil held at the chest, face hidden "
              "in shadow, front view, symmetrical, bone white and charcoal, "
              "smooth shading"),
        tam=(64, 84), estilo=50, outline="single color black outline",
        shading="detailed shading", detail="medium detail"),
    # mesma direção, três tamanhos — o eixo que o autor pediu
    "sigilo-32": dict(
        ref="carmim", desc=SIGILO + ", bone white and charcoal, smooth shading",
        tam=(64, 84), estilo=45, outline="selective outline",
        shading="detailed shading", detail="medium detail"),
    "sigilo-39": dict(
        ref="carmim", desc=SIGILO + ", bone white and charcoal, smooth shading",
        tam=(78, 104), estilo=45, outline="selective outline",
        shading="detailed shading", detail="medium detail"),
    "sigilo-48": dict(
        ref="carmim", desc=SIGILO + ", bone white and charcoal, many shades, "
                                    "soft gradients on the cloth",
        tam=(96, 128), estilo=45, outline="selective outline",
        shading="highly detailed shading", detail="highly detailed"),
    # o mesmo tamanho grande, sem contorno duro — costuma ler mais macio
    "sigilo-39-macio": dict(
        ref="bruma", desc=SIGILO + ", muted greys, no hard outline, form "
                                   "defined by soft value transitions",
        tam=(78, 104), estilo=50, outline="lineless",
        shading="highly detailed shading", detail="highly detailed"),
}


# ------------------------------------------------------------------ chave --

def chave() -> str:
    k = os.environ.get("PIXELLAB_API_KEY", "").strip()
    if k:
        return k
    if ARQ_CHAVE.exists():
        modo = ARQ_CHAVE.stat().st_mode & 0o777
        if modo & 0o077:
            print(f"aviso: {ARQ_CHAVE} está com modo {modo:o}; "
                  f"considere chmod 600", file=sys.stderr)
        return ARQ_CHAVE.read_text(encoding="utf-8").strip()
    sys.exit("sem chave. Defina PIXELLAB_API_KEY ou grave em "
             f"{ARQ_CHAVE} (chmod 600).")


def _post(rota: str, corpo: dict, timeout: int = 300) -> dict:
    req = urllib.request.Request(
        f"{BASE}{rota}", data=json.dumps(corpo).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {chave()}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"HTTP {e.code} em {rota}: {detalhe}") from None
    except urllib.error.URLError as e:
        raise SystemExit(f"não consegui falar com {BASE}: {e.reason}") from None


def saldo() -> dict:
    req = urllib.request.Request(
        f"{BASE}/balance", headers={"Authorization": f"Bearer {chave()}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode()[:300]}") from None


# ------------------------------------------------------------ referências --

def ref_base64(caminho: Path, larg: int, alt: int,
               corte_rodape: float = 0.06) -> str:
    """Referência em PNG com EXATAMENTE (larg, alt), pronta para style_image.

    A API exige que o style_image tenha as mesmas dimensões da saída pedida
    (`style_image must be size (200, 132)`). Por isso recorta ao centro na
    proporção alvo e só então redimensiona: esticar deformaria o manto, que é
    justamente a forma que se quer transferir.

    Corta a faixa inferior antes de tudo porque uma das referências tem marca
    d'água do autor original ali — e o que se quer da imagem é o ESTILO, não
    o desenho.
    """
    from PIL import Image
    im = Image.open(caminho).convert("RGB")
    if corte_rodape > 0:
        im = im.crop((0, 0, im.width, int(im.height * (1 - corte_rodape))))

    prop_alvo = larg / alt
    prop_atual = im.width / im.height
    if prop_atual > prop_alvo:                 # larga demais: corta os lados
        nova_l = int(im.height * prop_alvo)
        x = (im.width - nova_l) // 2
        im = im.crop((x, 0, x + nova_l, im.height))
    elif prop_atual < prop_alvo:               # alta demais: corta em baixo,
        nova_a = int(im.width / prop_alvo)     # preservando a cabeça
        im = im.crop((0, 0, im.width, nova_a))

    im = im.resize((larg, alt), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --------------------------------------------------------------- geração --

def gera(nome: str, v: dict, semente: int | None) -> Path:
    ref = REFERENCIAS[v["ref"]]
    if not ref.exists():
        raise SystemExit(f"referência não encontrada: {ref}")
    larg, alt = v["tam"]
    corpo = {
        "description": v["desc"],
        "negative_description": EVITAR,
        "image_size": {"width": larg, "height": alt},
        "style_image": {"type": "base64",
                        "base64": ref_base64(ref, larg, alt)},
        "style_strength": v["estilo"],
        "outline": v["outline"],
        "shading": v["shading"],
        "detail": v["detail"],
        "view": "side",
        "direction": "south",
        "no_background": True,
        "text_guidance_scale": 9.0,
    }
    if semente is not None:
        corpo["seed"] = semente

    t0 = time.time()
    d = _post("/generate-image-bitforge", corpo)
    b64 = (d.get("image") or {}).get("base64", "")
    if not b64:
        raise SystemExit(f"resposta sem imagem: {json.dumps(d)[:300]}")

    SAIDA.mkdir(parents=True, exist_ok=True)
    alvo = SAIDA / f"{nome}.png"
    alvo.write_bytes(base64.b64decode(b64))
    uso = d.get("usage") or {}
    print(f"  {nome:<12} {larg}x{alt}  {time.time()-t0:5.1f}s  "
          f"{alvo}  {uso}")
    return alvo


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--saldo", action="store_true")
    ap.add_argument("--lote", action="store_true", help="gera todas")
    ap.add_argument("--so", default="", help="gera só esta variante")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()

    if a.listar:
        for n, v in VARIANTES.items():
            print(f"{n:<12} ref={v['ref']:<8} {v['tam'][0]}x{v['tam'][1]}  "
                  f"estilo={v['estilo']}")
        return 0
    if a.saldo:
        print(json.dumps(saldo(), indent=2, ensure_ascii=False))
        return 0

    alvos = ([a.so] if a.so else list(VARIANTES)) if (a.so or a.lote) else []
    if not alvos:
        ap.print_help()
        return 1
    for n in alvos:
        if n not in VARIANTES:
            print(f"variante desconhecida: {n}. Há: {', '.join(VARIANTES)}")
            return 1

    print(f"gerando {len(alvos)} variante(s) em {SAIDA}")
    for n in alvos:
        try:
            gera(n, VARIANTES[n], a.seed)
        except SystemExit as e:
            print(f"  {n:<12} FALHOU: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
