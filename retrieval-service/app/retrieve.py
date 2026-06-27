from app.zim_search import ZimSearch
from app.snippet import strip_html, extract_snippet


def build_results(zs: ZimSearch, query: str, k: int) -> list[dict]:
    results = []
    for hit in zs.search(query, k):
        text = strip_html(zs.get_content(hit.path))
        results.append({
            "title": hit.title,
            "url": hit.path,
            "snippet": extract_snippet(text, query),
        })
    return results
