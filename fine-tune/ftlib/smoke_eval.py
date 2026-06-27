import json, urllib.request
from ftlib.schema import is_valid_hint
from ftlib.format_chatml import TUTOR_SYSTEM

def extract_json(raw: str):
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except Exception:
        return None

def score(records: list[dict], asker) -> dict:
    tutor = [r for r in records if r["messages"][0]["content"] == TUTOR_SYSTEM]
    valid = 0
    for r in tutor:
        # manda só system+user (sem o assistant de referência)
        prompt = [r["messages"][0], r["messages"][1]]
        reply = asker(prompt)
        if is_valid_hint(extract_json(reply or "")):
            valid += 1
    total = len(tutor)
    return {"total": total, "valid": valid, "frac": (valid / total) if total else 0.0}

def _ollama_asker(model: str, url: str):
    def ask(messages):
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["message"]["content"]
    return ask

def main():
    import sys
    with open("data/heldout.jsonl", encoding="utf-8") as f:
        held = [json.loads(l) for l in f if l.strip()]
    asker = _ollama_asker("professor-ft", "http://localhost:11434")
    out = score(held, asker)
    print(f"smoke-eval: {out['valid']}/{out['total']} JSON válido (frac={out['frac']:.2f})")
    sys.exit(0 if out["frac"] >= 0.5 else 1)

if __name__ == "__main__":
    main()
