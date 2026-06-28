"""System prompts canônicos (espelham src/core) e validação de panorama.
A dica reusa TUTOR_SYSTEM; o panorama reusa PANORAMA_SYSTEM — ambos de ftlib
(fonte única), espelhando src/core. Aqui só re-exportamos e construímos mensagens."""
import json
from ftlib.format_chatml import TUTOR_SYSTEM, PANORAMA_SYSTEM

HINT_SYSTEM = TUTOR_SYSTEM


def build_hint_messages(code: str, lang: str) -> list:
    return [
        {"role": "system", "content": HINT_SYSTEM},
        {"role": "user", "content": f"Linguagem: {lang}\nCódigo:\n{code}"},
    ]


def build_panorama_messages(outline: str, lang: str) -> list:
    return [
        {"role": "system", "content": PANORAMA_SYSTEM},
        {"role": "user", "content": f"Linguagem: {lang}\nEsqueleto do arquivo:\n{outline}"},
    ]


def is_valid_panorama(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("skip") is True:
        return True
    return (isinstance(obj.get("structure"), str) and obj["structure"].strip()
            and isinstance(obj.get("next"), str) and obj["next"].strip())


def parse_panorama(raw: str):
    """Estrito (espelha parsePanorama do TS): só {structure, next}; skip -> None."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(raw[start:end + 1])
    except Exception:
        return None
    if isinstance(obj, dict) and obj.get("skip") is True:
        return None
    if (isinstance(obj, dict) and isinstance(obj.get("structure"), str)
            and isinstance(obj.get("next"), str)):
        return {"structure": obj["structure"], "next": obj["next"]}
    return None
