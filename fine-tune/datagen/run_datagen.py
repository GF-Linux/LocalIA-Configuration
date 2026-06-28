"""Orquestrador: piloto -> projeção de custo/QA -> escala até o teto.
`run_generation` e `pilot_projection` são puros/testáveis; `main` é glue (gasta API)."""
import argparse
import json
import os
import sys
import threading

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


def scale_concurrent(items, ask, budget, kind, out_path, *, workers=8,
                     max_skip_ratio=0.3, progress_every=25):
    """Escala com chamadas CONCORRENTES (GLM 5.2 é ~4s/call -> paraleliza p/ minutos,
    não horas), persistência INCREMENTAL (append+flush por linha -> crash-safe e
    retomável; dá pra ver o arquivo crescer) e dedup/balance online.

    `ask` deve ter `on_usage` já encadeado a um charge THREAD-SAFE (lock externo).
    Para limpo quando `budget.over()`. Retorna (existing_rows, fresh)."""
    existing_rows = _load_existing(out_path)
    seen = {_row_key(r) for r in existing_rows}
    field = "hint" if kind == "hint" else "panorama"
    fresh = []
    lock = threading.Lock()
    stop = threading.Event()  # erro não-recuperável (ex.: 402 sem crédito) para tudo limpo
    item_iter = iter(items)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fout = open(out_path, "a", encoding="utf-8")

    def _is_skip(row):
        return isinstance(row[field], dict) and row[field].get("skip") is True

    def worker():
        while not stop.is_set():
            with lock:
                if budget.over():
                    return
                item = next(item_iter, None)
                # dedup PRÉ-geração: se o código/outline já está no arquivo (ou já saiu
                # nesta run), pula SEM gastar uma chamada GLM (re-runs não pagam dup).
                while item is not None and _row_key(item) in seen:
                    item = next(item_iter, None)
                if item is None:
                    return
                seen.add(_row_key(item))  # reserva a chave p/ não duplicar entre threads
            try:
                row = generate_one(item, ask, kind)  # rede FORA do lock
            except Exception as e:
                # GLM falhou após retries (ex.: 402 Payment Required, esgotou crédito).
                # Para TODAS as threads limpo — o que já foi salvo (incremental) persiste.
                with lock:
                    if not stop.is_set():
                        print(f"[escala] parando: erro não-recuperável do GLM: "
                              f"{str(e)[:120]}", file=sys.stderr, flush=True)
                    stop.set()
                return
            if row is None:
                continue  # parse/schema inválido (a chave fica reservada em `seen`)
            with lock:
                # a chave já foi reservada em `seen` antes da geração (dedup pré-call).
                # balance online: só aceita um skip se mantiver a razão <= teto
                if _is_skip(row):
                    n_skip = sum(1 for r in fresh if _is_skip(r))
                    if fresh and (n_skip + 1) / (len(fresh) + 1) > max_skip_ratio:
                        continue
                fresh.append(row)
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")
                fout.flush()
                if len(fresh) % progress_every == 0:
                    print(f"[escala] {len(fresh)} válidos  spent=${budget.spent():.3f}",
                          file=sys.stderr, flush=True)

    try:
        threads = [threading.Thread(target=worker) for _ in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        fout.close()
    return existing_rows, fresh


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
    ap.add_argument("--workers", type=int, default=8, help="chamadas GLM concorrentes na escala")
    ap.add_argument("--reasoning", action="store_true",
                    help="liga o reasoning do GLM (mais lento/caro, qualidade maior)")
    ap.add_argument("--max-tokens", type=int, default=512,
                    help="cap de tokens de saída (use ~2048 com --reasoning p/ não truncar)")
    a = ap.parse_args(argv)

    # Pré-flight: a QA usa o juiz Claude (_judge_ask -> ANTHROPIC_API_KEY + SDK anthropic).
    # Falhe ANTES de gastar dinheiro no GLM se a chave OU o SDK estiverem ausentes.
    # (OPENROUTER_API_KEY já é validada cedo por make_glm_ask.)
    if a.kind == "hint" and a.qa > 0:
        import importlib.util
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY ausente: a QA (juiz Claude) rodaria após a geração e "
                "abortaria depois de gastar no GLM. Defina ANTHROPIC_API_KEY ou rode com --qa 0."
            )
        if importlib.util.find_spec("anthropic") is None:
            raise RuntimeError(
                "Pacote 'anthropic' não instalado neste venv: a QA (juiz Claude) abortaria "
                "após gastar no GLM. Instale 'anthropic' (ex.: pip install anthropic==0.69.0) "
                "ou rode com --qa 0."
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
        ask = make_glm_ask(GLM_MODEL, on_usage=budget.charge,
                           max_tokens=a.max_tokens, reasoning_enabled=a.reasoning)
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
    # Geração concorrente + persistência incremental (ver scale_concurrent). O charge
    # do budget é serializado por um lock, pois várias threads o atualizam.
    budget = Budget(ceiling_usd=ceiling, price=GLM52_PRICE)
    charge_lock = threading.Lock()

    def _locked_charge(usage):
        with charge_lock:
            budget.charge(usage)

    ask = make_glm_ask(GLM_MODEL, on_usage=_locked_charge,
                       max_tokens=a.max_tokens, reasoning_enabled=a.reasoning)
    existing_rows, fresh = scale_concurrent(
        items, ask, budget, a.kind, out_path,
        workers=a.workers, max_skip_ratio=a.max_skip_ratio,
    )

    report = {"mode": "scale", "kind": a.kind, "spent": round(budget.spent(), 4),
              "written": len(fresh), "total_now": len(existing_rows) + len(fresh),
              "by_lang": counts_by(fresh, lambda r: r["lang"]),
              "tokens": {"prompt": budget.prompt_tokens, "completion": budget.completion_tokens}}
    if a.kind == "hint" and a.qa > 0:
        report["qa"] = qa_report(fresh, _judge_ask(), n=a.qa, seed=a.seed)
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
