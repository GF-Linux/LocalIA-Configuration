"""Controle de qualidade puro: dedup por código normalizado e balanceamento de razão."""
import random
import re


def normalize_code(code: str) -> str:
    return re.sub(r"\s+", " ", code).strip()


def _default_key(row: dict) -> str:
    return normalize_code(row.get("code") or row.get("outline") or "")


def dedup(rows, key=None) -> list:
    key = key or _default_key
    seen = set()
    out = []
    for r in rows:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def counts_by(rows, bucket_of) -> dict:
    c = {}
    for r in rows:
        b = bucket_of(r)
        c[b] = c.get(b, 0) + 1
    return c


def balance_by_ratio(rows, predicate, max_ratio: float, *, seed: int = 0) -> list:
    """Limita a fração de linhas com predicate=True a max_ratio do total mantido.
    Mantém todas as linhas com predicate=False; amostra as True (seed) até o cap.
    Preserva a ordem original."""
    if max_ratio >= 1:
        return list(rows)
    yes = [r for r in rows if predicate(r)]
    no = [r for r in rows if not predicate(r)]
    # cap = maior y tal que y / (y + len(no)) <= max_ratio
    cap = int(max_ratio / (1 - max_ratio) * len(no))
    if len(yes) <= cap:
        return list(rows)
    shuffled = yes[:]
    random.Random(seed).shuffle(shuffled)
    keep_ids = {id(r) for r in shuffled[:cap]}
    return [r for r in rows if (not predicate(r)) or id(r) in keep_ids]
