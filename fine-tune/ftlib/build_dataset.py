import json, random
from ftlib.collect_seeds import load_seeds
from ftlib.format_chatml import seed_to_chatml, oci_to_chatml

def split_deterministic(items, frac_heldout, seed):
    rng = random.Random(seed)
    shuffled = items[:]
    rng.shuffle(shuffled)
    n_held = round(len(shuffled) * frac_heldout)
    heldout = shuffled[:n_held]
    train = shuffled[n_held:]
    return train, heldout

def _read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]

def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def main():
    seeds = [seed_to_chatml(s) for s in load_seeds("data/seeds.jsonl")]
    oci = [oci_to_chatml(r) for r in _read_jsonl("data/oci.jsonl")]
    items = seeds + oci
    train, heldout = split_deterministic(items, 0.15, seed=42)
    _write_jsonl("data/train.jsonl", train)
    _write_jsonl("data/heldout.jsonl", heldout)
    print(f"train={len(train)} heldout={len(heldout)} (seeds={len(seeds)} oci={len(oci)})")

if __name__ == "__main__":
    main()
