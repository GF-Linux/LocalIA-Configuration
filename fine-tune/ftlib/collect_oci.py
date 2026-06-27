import argparse, json

def normalize_oci_row(row: dict) -> dict | None:
    inp = row.get("input")
    out = row.get("output")
    if not (isinstance(inp, str) and inp.strip() and isinstance(out, str) and out.strip()):
        return None
    return {"instruction": inp, "response": out}

def main(n: int, out_path: str) -> int:
    from datasets import load_dataset
    ds = load_dataset("nvidia/OpenCodeInstruct", split="train", streaming=True)
    written = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for row in ds:
            norm = normalize_oci_row(row)
            if norm is None:
                continue
            f.write(json.dumps(norm, ensure_ascii=False) + "\n")
            written += 1
            if written >= n:
                break
    return written

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default="data/oci.jsonl")
    a = ap.parse_args()
    print("escritas:", main(a.n, a.out))
