"""QA por juiz: amostra dicas ensináveis e roda a rubrica Claude da B1.
Reusa eval/evallib/rubric.score_quality (juiz injetável). O diretório `eval`
é adicionado ao sys.path como `eval/evallib/contract.py` faz com `fine-tune`."""
import json
import os
import random
import sys

_EVAL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "eval"))
if _EVAL not in sys.path:
    sys.path.insert(0, _EVAL)

from evallib.rubric import score_quality  # noqa: E402


def _is_skip(obj) -> bool:
    return isinstance(obj, dict) and obj.get("skip") is True


def _counts_by_lang(rows) -> dict:
    c = {}
    for r in rows:
        lang = r.get("lang", "?")
        c[lang] = c.get(lang, 0) + 1
    return c


def qa_report(rows, judge_ask, *, n: int = 20, seed: int = 0) -> dict:
    teachable = [r for r in rows if isinstance(r.get("hint"), dict) and not _is_skip(r["hint"])]
    sample = teachable[:]
    random.Random(seed).shuffle(sample)
    sample = sample[:n]
    items = [({"code": r["code"], "lang": r["lang"]},
              json.dumps(r["hint"], ensure_ascii=False)) for r in sample]
    rubric = (score_quality(items, judge_ask) if items
              else {"n": 0, "valid": 0, "means": {}, "overall": 0.0})
    n_total = len(rows)
    n_skip = sum(1 for r in rows if _is_skip(r.get("hint")))
    return {
        "n_total": n_total,
        "skip_rate": (n_skip / n_total) if n_total else 0.0,
        "n_judged": rubric["valid"],
        "rubric": rubric["means"],
        "overall": rubric["overall"],
        "by_lang": _counts_by_lang(rows),
    }
