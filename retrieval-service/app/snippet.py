import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

def strip_html(html: str) -> str:
    return _WS.sub(" ", _TAG.sub(" ", html)).strip()

def extract_snippet(text: str, query: str, max_chars: int = 240) -> str:
    if not text:
        return ""
    lower = text.lower()
    pos = -1
    for term in query.lower().split():
        pos = lower.find(term)
        if pos != -1:
            break
    if pos == -1:
        snip = text[:max_chars]
        return snip + ("…" if len(text) > max_chars else "")
    start = max(0, pos - max_chars // 3)
    end = min(len(text), start + max_chars)
    snip = text[start:end]
    if start > 0:
        snip = "…" + snip
    if end < len(text):
        snip = snip + "…"
    # Trim if exceeds tolerance to stay within max_chars + 1
    if len(snip) > max_chars + 1:
        snip = snip[:max_chars + 1]
    return snip
