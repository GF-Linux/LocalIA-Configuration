"""Régua do Professor (B1). Roda as 4 trilhas para o modelo fine-tunado e o base,
e imprime o veredito de promoção. Trilhas caras (juiz/API) podem ser puladas com flags.

Pré-requisitos:
  - Ollama local com os modelos (ex.: professor-ft e qwen2.5-coder:14b).
  - ANTHROPIC_API_KEY no ambiente (para as trilhas de juiz/A-B). NÃO commitar a chave.

Uso:
  python run_eval.py --ft professor-ft --base qwen2.5-coder:14b
  python run_eval.py --ft professor-ft --base qwen2.5-coder:14b --no-judge  # só T0+T3 (sem API)
"""
import argparse
import json
import os
import sys

from evallib.probes import load_probes
from evallib.runners import make_ollama_ask, generate_hints, score_format, score_selectivity
from evallib.rubric import score_quality
from evallib.abtest import compare
from evallib.codegen import (build_code_prompt, strip_code_fence, make_ollama_code_ask,
                             load_subset_ids, pass_at_1)
from evallib.sandbox import subprocess_executor
from evallib.score import compute_gates, verdict, format_report

OLLAMA_URL = "http://localhost:11434"

def _code_pass_at_1(model, problems):
    code_ask = make_ollama_code_ask(model, OLLAMA_URL)
    completions = [strip_code_fence(code_ask(build_code_prompt(p))) for p in problems]
    return pass_at_1(problems, completions, subprocess_executor(timeout=10.0))["frac"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ft", required=True, help="nome do modelo fine-tunado no Ollama")
    ap.add_argument("--base", required=True, help="nome do modelo base no Ollama")
    ap.add_argument("--no-judge", action="store_true", help="pula T1+T2 (não usa a API do Claude)")
    a = ap.parse_args()

    probes = load_probes("data/probes.jsonl")

    # T0 — gerar dicas (ft e base) e medir formato/seletividade
    ft_ask = make_ollama_ask(a.ft, OLLAMA_URL)
    base_ask = make_ollama_ask(a.base, OLLAMA_URL)
    hints_ft = generate_hints(probes, ft_ask)
    hints_base = generate_hints(probes, base_ask)
    fmt_ft = score_format(probes, hints_ft)
    fmt_base = score_format(probes, hints_base)
    sel = score_selectivity(probes, hints_ft)

    # T1 + T2 — juiz (Claude). Só se houver chave e sem --no-judge.
    if a.no_judge:
        quality = {"overall_ft": 0.0, "overall_base": 0.0}
        ab = {"ft_wins": 0, "base_wins": 0, "ties": 0}
        print("[aviso] --no-judge: T1/T2 não rodaram; G1 será reprovado por padrão.", file=sys.stderr)
    else:
        from evallib.judge import make_claude_ask
        # T1 (qualidade) é só sobre probes ENSINÁVEIS (não-skip): pontuar {"skip":true}
        # numa rubrica de 1-5 não faz sentido e poluiria o sinal de G1.
        teachable = [(p, hf, hb) for p, hf, hb in zip(probes, hints_ft, hints_base)
                     if not p["should_skip"]]
        n_calls = len(teachable) * 2 + len(probes)  # T1 ft + T1 base (ensináveis) + T2 (todos)
        print(f"[info] vou fazer ~{n_calls} chamadas ao Claude (juiz). Ctrl-C para abortar.", file=sys.stderr)
        judge_ask = make_claude_ask()
        q_ft = score_quality([(p, hf) for p, hf, _ in teachable], judge_ask)
        q_base = score_quality([(p, hb) for p, _, hb in teachable], judge_ask)
        quality = {"overall_ft": q_ft["overall"], "overall_base": q_base["overall"]}
        ab = compare(probes, hints_ft, hints_base, judge_ask, seed=42)

    # T3 — regressão de código (HumanEval subset)
    from datasets import load_dataset
    ds = load_dataset("openai_humaneval", split="test")
    wanted = set(load_subset_ids("data/humaneval_subset.txt"))
    problems = [r for r in ds if r["task_id"] in wanted]
    code_ft = _code_pass_at_1(a.ft, problems)
    code_base = _code_pass_at_1(a.base, problems)

    results = {
        "format": {"ft": fmt_ft["frac"], "base": fmt_base["frac"]},
        "quality": quality,
        "ab": ab,
        "code": {"ft": code_ft, "base": code_base},
        "selectivity": {"correct": sel["correct"], "total": sel["total"]},
    }
    gates = compute_gates(results)
    report = format_report(results, gates)
    print(report)

    os.makedirs("reports", exist_ok=True)
    with open("reports/last.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "gates": gates, "verdict": verdict(gates)},
                  f, ensure_ascii=False, indent=2)

    sys.exit(0 if verdict(gates) == "PROMOVER" else 1)

if __name__ == "__main__":
    main()
