import json, os, random
from ftlib.collect_seeds import load_seeds
from ftlib.format_chatml import seed_to_chatml, oci_to_chatml, panorama_to_chatml

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

def _maybe_read(path):
    return _read_jsonl(path) if os.path.exists(path) else []

def build_items(seeds_path, oci_path, gen_hints_path, gen_panorama_path):
    seeds = [seed_to_chatml(s) for s in load_seeds(seeds_path)]
    oci = [oci_to_chatml(r) for r in _read_jsonl(oci_path)]
    # dicas geradas têm o mesmo shape {code,lang,hint} -> reusa seed_to_chatml
    gen_hints = [seed_to_chatml(r) for r in _maybe_read(gen_hints_path)]
    gen_panorama = [panorama_to_chatml(r) for r in _maybe_read(gen_panorama_path)]
    return seeds + oci + gen_hints + gen_panorama

def main():
    items = build_items(
        "data/seeds.jsonl", "data/oci.jsonl",
        "data/generated_hints.jsonl", "data/generated_panorama.jsonl",
    )
    train, heldout = split_deterministic(items, 0.15, seed=42)
    _write_jsonl("data/train.jsonl", train)
    _write_jsonl("data/heldout.jsonl", heldout)
    print(f"train={len(train)} heldout={len(heldout)} (total={len(items)})")

if __name__ == "__main__":
    main()
