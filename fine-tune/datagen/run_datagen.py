"""Orquestrador: piloto -> projeção de custo/QA -> escala até o teto.
`run_generation` e `pilot_projection` são puros/testáveis; `main` é glue (gasta API)."""
import argparse
import json
import os

from datagen.budget import Budget, project_total, GLM52_PRICE
from datagen.generate import generate_one
from datagen.quality import normalize_code


def _row_key(r: dict) -> str:
    """Chave de dedup consistente com `quality.dedup`: código/outline normalizado
    (ignora a anotação do GLM, que varia entre regenerações do mesmo código)."""
    return normalize_code(r.get("code") or r.get("outline") or "")


def dedup_against_existing(existing_rows, new_rows) -> list:
    """Filtra `new_rows`, descartando linhas cujo código/outline normalizado já
    aparece em `existing_rows` (dedup cross-run para append idempotente)."""
    seen = {_row_key(r) for r in existing_rows}
    out = []
    for r in new_rows:
        k = _row_key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def run_generation(items, ask, budget: Budget, kind: str) -> list:
    out = []
    for item in items:
        if budget.over():
            break
        row = generate_one(item, ask, kind)
        if row is not None:
            out.append(row)
    return out


def pilot_projection(budget: Budget, n_valid: int, ceiling: float) -> dict:
    spent = budget.spent()
    per = (spent / n_valid) if n_valid else 0.0
    return {
        "spent": round(spent, 4),
        "n_valid": n_valid,
        "per_valid": round(per, 5),
        "projected_valid_for_ceiling": project_total(spent, n_valid, ceiling),
    }


# ---- glue (gasta API; não unit-testado) ----

def _append_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _load_existing(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main(argv=None):
    from datagen.openrouter import make_glm_ask, GLM_MODEL
    from datagen.codesource import (
        iter_code_search_net, make_outline, sample_code, CSN_LANGS,
    )
    from datagen.quality import dedup, balance_by_ratio, counts_by
    from datagen.qa_sample import qa_report

    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["hint", "panorama"], default="hint")
    ap.add_argument("--pilot", type=int, default=0, help="gera N exemplos e projeta custo")
    ap.add_argument("--budget", type=float, default=0.0, help="teto USD para a escala")
    ap.add_argument("--langs", default=",".join(CSN_LANGS))
    ap.add_argument("--per-lang", type=int, default=2000)
    ap.add_argument("--max-skip-ratio", type=float, default=0.3)
    ap.add_argument("--qa", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    # Pré-flight: a QA usa o juiz Claude (_judge_ask -> ANTHROPIC_API_KEY). Falhe ANTES
    # de gastar dinheiro no GLM se a chave estiver ausente. (OPENROUTER_API_KEY já é
    # validada cedo por make_glm_ask.)
    if a.kind == "hint" and a.qa > 0 and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY ausente: a QA (juiz Claude) rodaria após a geração e "
            "abortaria depois de gastar no GLM. Defina ANTHROPIC_API_KEY ou rode com --qa 0."
        )

    ceiling = a.budget if a.budget > 0 else 4.0

    langs = tuple(s.strip() for s in a.langs.split(",") if s.strip())
    raw = sample_code(iter_code_search_net(langs, a.per_lang),
                      n=(a.pilot or 10_000), seed=a.seed)
    if a.kind == "panorama":
        items = [{"outline": make_outline(r["code"], r["lang"]), "lang": r["lang"]} for r in raw]
        out_path = "data/generated_panorama.jsonl"
    else:
        items = raw
        out_path = "data/generated_hints.jsonl"

    if a.pilot:
        budget = Budget(ceiling_usd=1e9, price=GLM52_PRICE)
        ask = make_glm_ask(GLM_MODEL, on_usage=budget.charge)
        valids = run_generation(items[:a.pilot], ask, budget, a.kind)
        proj = pilot_projection(budget, len(valids), ceiling)
        report = {"mode": "pilot", "kind": a.kind, "projection": proj,
                  "tokens": {"prompt": budget.prompt_tokens, "completion": budget.completion_tokens},
                  "yield": f"{len(valids)}/{a.pilot}"}
        if a.kind == "hint":
            report["qa"] = qa_report(valids, _judge_ask(), n=a.qa, seed=a.seed)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        _write_report(report)
        print(f"[piloto] yield={len(valids)}/{a.pilot}  spent=${proj['spent']}  "
              f"-> ~{proj['projected_valid_for_ceiling']} válidos para ${ceiling}")
        return

    # escala — o teto real (ceiling, default $4) é sempre aplicado, senão um run sem
    # --budget geraria sobre a amostra inteira (n=10_000) sem freio de custo.
    budget = Budget(ceiling_usd=ceiling, price=GLM52_PRICE)
    ask = make_glm_ask(GLM_MODEL, on_usage=budget.charge)
    valids = run_generation(items, ask, budget, a.kind)
    valids = dedup(valids)
    # balance_by_ratio limita a razão de skip POR run; balanceamento cumulativo entre
    # múltiplos runs de escala está fora do escopo (escala é single-run por kind).
    if a.kind == "hint":
        valids = balance_by_ratio(valids, lambda r: r["hint"].get("skip") is True,
                                  a.max_skip_ratio, seed=a.seed)
    else:
        valids = balance_by_ratio(valids, lambda r: r["panorama"].get("skip") is True,
                                  a.max_skip_ratio, seed=a.seed)
    # dedup contínuo contra o que já existe — chaveado pelo código/outline normalizado
    # (não pelo JSON da linha inteira, que muda a cada regeneração da anotação).
    existing_rows = _load_existing(out_path)
    fresh = dedup_against_existing(existing_rows, valids)
    _append_jsonl(out_path, fresh)

    report = {"mode": "scale", "kind": a.kind, "spent": round(budget.spent(), 4),
              "written": len(fresh), "total_now": len(existing_rows) + len(fresh),
              "by_lang": counts_by(valids, lambda r: r["lang"]),
              "tokens": {"prompt": budget.prompt_tokens, "completion": budget.completion_tokens}}
    if a.kind == "hint":
        report["qa"] = qa_report(valids, _judge_ask(), n=a.qa, seed=a.seed)
    _write_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _judge_ask():
    """Juiz Claude da B1 (reusa eval/evallib/judge.make_claude_ask)."""
    import os, sys
    eval_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "eval"))
    if eval_dir not in sys.path:
        sys.path.insert(0, eval_dir)
    from evallib.judge import make_claude_ask
    return make_claude_ask()


def _write_report(report):
    os.makedirs("reports", exist_ok=True)
    with open("reports/datagen.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
