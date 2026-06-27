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
    lead = "…" if start > 0 else ""
    # reserve room for the leading and (possible) trailing ellipsis
    budget = max_chars - len(lead)
    end = min(len(text), start + budget)
    trail = "…" if end < len(text) else ""
    # if a trailing ellipsis is needed, shrink the window by 1 more to make room
    if trail and end == start + budget:
        end -= 1
    return lead + text[start:end] + trail
