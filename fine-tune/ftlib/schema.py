HINT_KEYS = ("comment", "why", "nudge", "suggestion")

def is_valid_hint(obj) -> bool:
    if not isinstance(obj, dict):
        return False
    if obj.get("skip") is True:
        return True
    return all(isinstance(obj.get(k), str) and obj.get(k).strip() for k in HINT_KEYS)
