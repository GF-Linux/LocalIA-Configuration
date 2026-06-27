import random
from evallib.contract import extract_json

_INSTR = (
    "Duas dicas de tutor para o mesmo trecho de código. Escolha a MELHOR como ensino "
    "(mais didática, ensina o porquê sem entregar a solução, concisa e correta). "
    'Responda SOMENTE em JSON: {"winner": "A"} ou {"winner": "B"} ou {"winner": "tie"}.'
)

def build_pair(probe: dict, hint_ft: str, hint_base: str, rng: random.Random):
    # randomiza qual modelo recebe o rótulo A
    if rng.random() < 0.5:
        mapping = {"A": "ft", "B": "base"}
        a_text, b_text = hint_ft, hint_base
    else:
        mapping = {"A": "base", "B": "ft"}
        a_text, b_text = hint_base, hint_ft
    prompt = (
        f"{_INSTR}\n\n"
        f"Linguagem: {probe['lang']}\n"
        f"TRECHO:\n{probe['code']}\n\n"
        f"Resposta A:\n{a_text}\n\n"
        f"Resposta B:\n{b_text}"
    )
    return prompt, mapping

def parse_choice(raw: str):
    obj = extract_json(raw or "")
    if not isinstance(obj, dict):
        return None
    w = obj.get("winner")
    return w if w in ("A", "B", "tie") else None

def compare(probes, hints_ft, hints_base, ask, seed: int) -> dict:
    rng = random.Random(seed)
    ft_wins = base_wins = ties = valid = 0
    for probe, hf, hb in zip(probes, hints_ft, hints_base):
        prompt, mapping = build_pair(probe, hf, hb, rng)
        choice = parse_choice(ask(prompt))
        if choice is None:
            continue
        valid += 1
        if choice == "tie":
            ties += 1
        elif mapping[choice] == "ft":
            ft_wins += 1
        else:
            base_wins += 1
    return {"n": len(probes), "valid": valid,
            "ft_wins": ft_wins, "base_wins": base_wins, "ties": ties}
