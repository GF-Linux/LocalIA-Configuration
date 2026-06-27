import json
from ftlib.schema import is_valid_hint


def load_seeds(path: str) -> list[dict]:
    """Lê um arquivo JSONL de sementes de fine-tune e valida cada linha.

    Cada linha deve ser um objeto JSON com:
      - "code": str não-vazio
      - "lang": str não-vazio
      - "hint": dict válido segundo is_valid_hint (completo ou skip)

    Lança ValueError em qualquer linha inválida.
    """
    seeds = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not (isinstance(row.get("code"), str) and row["code"].strip()):
                raise ValueError(f"linha {i}: 'code' ausente/vazio")
            if not (isinstance(row.get("lang"), str) and row["lang"].strip()):
                raise ValueError(f"linha {i}: 'lang' ausente/vazio")
            if not is_valid_hint(row.get("hint")):
                raise ValueError(f"linha {i}: 'hint' inválido")
            seeds.append(row)
    return seeds
