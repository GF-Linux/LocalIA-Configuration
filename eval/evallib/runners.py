import json
import urllib.request
from evallib.contract import TUTOR_SYSTEM, is_valid_hint, extract_json

def build_tutor_messages(probe: dict) -> list[dict]:
    user = f"Linguagem: {probe['lang']}\nCódigo:\n{probe['code']}"
    return [
        {"role": "system", "content": TUTOR_SYSTEM},
        {"role": "user", "content": user},
    ]

def make_ollama_ask(model: str, url: str = "http://localhost:11434"):
    def ask(messages: list[dict]) -> str:
        body = json.dumps({"model": model, "messages": messages, "stream": False,
                           "options": {"temperature": 0}}).encode()
        req = urllib.request.Request(f"{url}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["message"]["content"]
    return ask

def generate_hints(probes, ask) -> list[str]:
    return [ask(build_tutor_messages(p)) for p in probes]

def score_format(probes, hints) -> dict:
    total = len(probes)
    valid = sum(1 for h in hints if is_valid_hint(extract_json(h or "")))
    return {"frac": (valid / total) if total else 0.0, "valid": valid, "total": total}

def score_selectivity(probes, hints) -> dict:
    correct = total = 0
    for p, h in zip(probes, hints):
        if not p.get("should_skip"):
            continue
        total += 1
        obj = extract_json(h or "")
        if isinstance(obj, dict) and obj.get("skip") is True:
            correct += 1
    return {"correct": correct, "total": total}
