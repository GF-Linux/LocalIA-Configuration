# Calibrado em 2026-06-27 após o 1º baseline real (filosofia "vitória clara":
# promove só se o ft for nitidamente melhor; margens resistem a ruído com n pequeno).
GATE_THRESHOLDS = {
    "format_min": 0.95,        # G0: piso absoluto de JSON válido do ft
    "code_eps": 0.05,          # G2: tolerância de regressão de código
    "ab_winrate_min": 0.60,    # G1: ft deve vencer >=60% das comparações A/B decididas
    "rubric_margin": 0.30,     # G1: rubrica do ft deve superar a do base por >= 0.30 (escala 1-5)
    "selectivity_min": 0.60,   # G3: deve calar em >=60% dos probes triviais
}

def compute_gates(results: dict) -> dict:
    fmt = results["format"]
    qual = results["quality"]
    ab = results["ab"]
    code = results["code"]
    sel = results["selectivity"]

    g0 = fmt["ft"] >= GATE_THRESHOLDS["format_min"]

    decided = ab["ft_wins"] + ab["base_wins"]
    ab_winrate = (ab["ft_wins"] / decided) if decided else 0.0
    g1 = (ab_winrate >= GATE_THRESHOLDS["ab_winrate_min"]) and \
         (qual["overall_ft"] >= qual["overall_base"] + GATE_THRESHOLDS["rubric_margin"])

    g2 = code["ft"] >= code["base"] - GATE_THRESHOLDS["code_eps"]
    g3 = sel["total"] > 0 and (sel["correct"] / sel["total"]) >= GATE_THRESHOLDS["selectivity_min"]
    return {"G0": g0, "G1": g1, "G2": g2, "G3": g3}

def verdict(gates: dict) -> str:
    return "PROMOVER" if all(gates.values()) else "NAO_PROMOVER"

def format_report(results: dict, gates: dict) -> str:
    fmt, qual, ab = results["format"], results["quality"], results["ab"]
    code, sel = results["code"], results["selectivity"]
    lines = [
        "=== Régua do Professor (B1) ===",
        f"T0 formato (JSON válido):  ft={fmt['ft']:.2f}  base={fmt['base']:.2f}   [G0={gates['G0']}]",
        f"T1 rubrica (média global): ft={qual['overall_ft']:.2f}  base={qual['overall_base']:.2f}",
        f"T2 A/B cego:  ft={ab['ft_wins']}  base={ab['base_wins']}  empates={ab['ties']}   [G1={gates['G1']}]",
        f"T3 código pass@1:  ft={code['ft']:.2f}  base={code['base']:.2f}   [G2={gates['G2']}]",
        f"Seletividade (deve calar): {sel['correct']}/{sel['total']}   [G3={gates['G3']}]",
        f">>> VEREDITO: {verdict(gates)}",
    ]
    return "\n".join(lines)
