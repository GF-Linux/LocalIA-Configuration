import json

_FIELDS_STR = ("id", "code", "lang", "teaching_point")

def load_probes(path: str) -> list[dict]:
    probes = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for k in _FIELDS_STR:
                if not (isinstance(row.get(k), str) and row[k].strip()):
                    raise ValueError(f"linha {i}: '{k}' ausente/vazio")
            if not isinstance(row.get("should_skip"), bool):
                raise ValueError(f"linha {i}: 'should_skip' deve ser bool")
            probes.append(row)
    return probes
