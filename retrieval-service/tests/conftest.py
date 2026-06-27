import pytest
from libzim.writer import Creator, Item, StringProvider, Hint


class _Article(Item):
    def __init__(self, path, title, html):
        super().__init__()
        self._path, self._title, self._html = path, title, html

    def get_path(self): return self._path
    def get_title(self): return self._title
    def get_mimetype(self): return "text/html"
    def get_contentprovider(self): return StringProvider(self._html)
    # DIFF from brief: enum member is FRONT_ARTICLE, not FRONTARTICLE
    def get_hints(self): return {Hint.FRONT_ARTICLE: True}


@pytest.fixture(scope="session")
def tiny_zim(tmp_path_factory):
    path = tmp_path_factory.mktemp("zim") / "tiny.zim"
    with Creator(str(path)).config_indexing(True, "eng") as c:
        c.add_item(_Article(
            "q1", "How to read a file in Python",
            "<html><body>Use the with open() context manager to read files safely "
            "so the file handle is always closed.</body></html>"))
        c.add_item(_Article(
            "q2", "List comprehension in Python",
            "<html><body>A list comprehension builds a list from an iterable "
            "in a single expression.</body></html>"))
        c.set_mainpath("q1")
    return str(path)
