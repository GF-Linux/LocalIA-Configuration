import json
import urllib.request

def build_code_prompt(problem: dict) -> str:
    return (
        "Complete a função abaixo. Responda SOMENTE com o corpo/código Python, "
        "sem explicações.\n\n" + problem["prompt"]
    )

def strip_code_fence(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.endswith("```"):
            s = s[: s.rfind("```")]
    return s.strip("\n")

def make_ollama_code_ask(model: str, url: str = "http://localhost:11434"):
    def ask(prompt: str) -> str:
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(f"{url}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read()).get("response", "")
    return ask

def load_subset_ids(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]

def pass_at_1(problems, completions, executor) -> dict:
    from evallib.sandbox import run_one
    passed = sum(1 for p, c in zip(problems, completions) if run_one(p, c, executor))
    total = len(problems)
    return {"passed": passed, "total": total, "frac": (passed / total) if total else 0.0}
