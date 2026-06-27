from evallib.contract import extract_json

RUBRIC_CRITERIA = ("socratic", "why", "concision", "relevance", "correctness")

_RUBRIC_TEXT = (
    "Avalie a DICA de um tutor de programação sobre o TRECHO do aluno, em 5 critérios, "
    "nota inteira de 1 (ruim) a 5 (ótimo):\n"
    "- socratic: dá um empurrão sem entregar a solução pronta (5) vs reescreve tudo (1).\n"
    "- why: explica o porquê/conceito (5) vs só aponta o erro (1).\n"
    "- concision: conciso e direto (5) vs prolixo (1).\n"
    "- relevance: específico ao trecho (5) vs genérico/fora de contexto (1).\n"
    "- correctness: tecnicamente correto (5) vs errado/enganoso (1).\n"
    'Responda SOMENTE em JSON: {"scores": {"socratic":n,"why":n,"concision":n,'
    '"relevance":n,"correctness":n}, "rationale": "..."}.'
)

def build_judge_prompt(probe: dict, hint_text: str) -> str:
    return (
        f"{_RUBRIC_TEXT}\n\n"
        f"Linguagem: {probe['lang']}\n"
        f"TRECHO:\n{probe['code']}\n\n"
        f"DICA DO MODELO:\n{hint_text}"
    )

def parse_verdict(raw: str):
    obj = extract_json(raw or "")
    if not isinstance(obj, dict):
        return None
    scores = obj.get("scores")
    if not isinstance(scores, dict):
        return None
    for c in RUBRIC_CRITERIA:
        v = scores.get(c)
        if not (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5):
            return None
    if not isinstance(obj.get("rationale"), str):
        return None
    return {"scores": {c: scores[c] for c in RUBRIC_CRITERIA}, "rationale": obj["rationale"]}

def score_quality(items, ask) -> dict:
    verdicts = []
    for probe, hint_text in items:
        v = parse_verdict(ask(build_judge_prompt(probe, hint_text)))
        if v is not None:
            verdicts.append(v)
    n = len(items)
    valid = len(verdicts)
    means = {}
    for c in RUBRIC_CRITERIA:
        means[c] = (sum(v["scores"][c] for v in verdicts) / valid) if valid else 0.0
    overall = (sum(means[c] for c in RUBRIC_CRITERIA) / len(RUBRIC_CRITERIA)) if valid else 0.0
    return {"n": n, "valid": valid, "means": means, "overall": overall}
