"""Gera um exemplo: monta prompt -> ask (GLM) -> parse -> valida schema.
Schema-gated: só retorna exemplos 100% válidos (descarta o resto)."""
from ftlib.schema import is_valid_hint
from ftlib.smoke_eval import extract_json
from datagen.prompts import (
    build_hint_messages, build_panorama_messages, is_valid_panorama,
)

# kind -> (builder(src, lang) -> messages, validator(obj) -> bool, src_key, out_field)
_KINDS = {
    "hint": (build_hint_messages, is_valid_hint, "code", "hint"),
    "panorama": (build_panorama_messages, is_valid_panorama, "outline", "panorama"),
}


def generate_one(item: dict, ask, kind: str):
    build, valid, src_key, out_field = _KINDS[kind]
    messages = build(item[src_key], item["lang"])
    obj = extract_json(ask(messages) or "")
    if valid(obj):
        return {**item, out_field: obj}
    return None


def generate_batch(items, ask, kind: str) -> list:
    out = []
    for item in items:
        row = generate_one(item, ask, kind)
        if row is not None:
            out.append(row)
    return out
