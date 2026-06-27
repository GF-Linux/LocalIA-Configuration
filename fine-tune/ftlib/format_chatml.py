import json

TUTOR_SYSTEM = (
    "Você é um professor de programação que ensina na prática, em português do Brasil. "
    "Olhe o trecho de código do aluno e, se houver UM ponto de aprendizado relevante, ensine "
    "o PORQUÊ e o idioma correto, sem reescrever todo o código. Se não houver nada que valha "
    "a pena ensinar, responda {\"skip\": true}. Responda SOMENTE em JSON válido no formato "
    "{\"comment\":\"...\",\"why\":\"...\",\"nudge\":\"...\",\"suggestion\":\"...\"}."
)

CODE_SYSTEM = "You are a helpful coding assistant. Answer the task with correct code."

def seed_to_chatml(seed: dict) -> dict:
    return {"messages": [
        {"role": "system", "content": TUTOR_SYSTEM},
        {"role": "user", "content": f"Linguagem: {seed['lang']}\nCódigo:\n{seed['code']}"},
        {"role": "assistant", "content": json.dumps(seed["hint"], ensure_ascii=False)},
    ]}

def oci_to_chatml(row: dict) -> dict:
    return {"messages": [
        {"role": "system", "content": CODE_SYSTEM},
        {"role": "user", "content": row["instruction"]},
        {"role": "assistant", "content": row["response"]},
    ]}
