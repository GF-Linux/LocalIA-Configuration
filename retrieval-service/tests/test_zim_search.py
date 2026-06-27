from app.zim_search import ZimSearch


def test_search_finds_relevant_article(tiny_zim):
    zs = ZimSearch(tiny_zim)
    hits = zs.search("read file open", k=3)
    assert len(hits) >= 1
    assert any("read a file" in h.title.lower() for h in hits)


def test_search_empty_query_returns_empty(tiny_zim):
    assert ZimSearch(tiny_zim).search("", k=3) == []


def test_get_content_returns_html(tiny_zim):
    zs = ZimSearch(tiny_zim)
    hit = zs.search("read file open", k=1)[0]
    content = zs.get_content(hit.path)
    assert "with open()" in content


def test_get_content_bad_path_returns_empty(tiny_zim):
    assert ZimSearch(tiny_zim).get_content("nonexistent/path") == ""
