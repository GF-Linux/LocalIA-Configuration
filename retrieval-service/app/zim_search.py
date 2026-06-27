from dataclasses import dataclass

from libzim.reader import Archive
from libzim.search import Query, Searcher


@dataclass
class SearchHit:
    path: str
    title: str


class ZimSearch:
    def __init__(self, zim_path: str):
        self._zim = Archive(zim_path)

    def search(self, query: str, k: int) -> list[SearchHit]:
        if not query.strip():
            return []
        q = Query().set_query(query)
        search = Searcher(self._zim).search(q)
        n = min(k, search.getEstimatedMatches())
        if n <= 0:
            return []
        hits: list[SearchHit] = []
        # getResults(start, count) yields entry paths (strings) in libzim 3.x
        for path in search.getResults(0, n):
            try:
                entry = self._zim.get_entry_by_path(path)
                hits.append(SearchHit(path=path, title=entry.title))
            except Exception:
                continue
        return hits

    def get_content(self, path: str) -> str:
        try:
            item = self._zim.get_entry_by_path(path).get_item()
            return bytes(item.content).decode("utf-8", errors="ignore")
        except Exception:
            return ""
