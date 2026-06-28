"""Amostragem de código real (puro) + loaders de dataset (glue).
A lógica testável opera sobre um iterável de {code, lang}; a fonte é plugável."""
import hashlib
import json
import random
import re

# Espelha src/core/outline.ts: linhas "estruturais" (assinaturas/topo) para o esqueleto.
_STRUCT = re.compile(
    r"^\s*(import |from |export |def |class |function |const |public |private |"
    r"let |var |type |interface |async |func )"
)


def make_outline(code: str, lang: str, max_lines: int = 120) -> str:
    lines = code.split("\n")
    if len(lines) <= max_lines:
        return code
    return "\n".join(l for l in lines if _STRUCT.match(l))


def normalize(code: str) -> str:
    return re.sub(r"\s+", " ", code).strip()


def _ok_size(code, min_chars: int, max_chars: int) -> bool:
    return isinstance(code, str) and min_chars <= len(code.strip()) <= max_chars


def sample_code(rows, n: int, *, seed: int = 0, min_chars: int = 40,
                max_chars: int = 2000) -> list:
    seen = set()
    picked = []
    for row in rows:
        code = row.get("code")
        lang = row.get("lang")
        if not (isinstance(lang, str) and lang.strip()):
            continue
        if not _ok_size(code, min_chars, max_chars):
            continue
        h = hashlib.sha1(normalize(code).encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        picked.append({"code": code, "lang": lang})
    random.Random(seed).shuffle(picked)
    return picked[:n]


# ---- loaders (glue; verificados ao vivo, não no pytest) ----

# code_search_net: código real multi-linguagem, rótulo de linguagem limpo.
CSN_LANGS = ("python", "java", "javascript", "go", "php", "ruby")


def iter_code_search_net(langs=CSN_LANGS, limit_per_lang: int = 2000):
    from datasets import load_dataset
    for lang in langs:
        ds = load_dataset("code_search_net", lang, split="train",
                          streaming=True, trust_remote_code=True)
        k = 0
        for row in ds:
            code = row.get("func_code_string") or row.get("whole_func_string")
            if isinstance(code, str) and code.strip():
                yield {"code": code, "lang": lang}
                k += 1
            if k >= limit_per_lang:
                break


def iter_oci(path: str):
    """Reusa a coleta OCI da Fatia A: a 'response' carrega código real."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            code = row.get("response")
            if isinstance(code, str) and code.strip():
                yield {"code": code, "lang": "unknown"}
