from app.snippet import strip_html, extract_snippet

def test_strip_html_removes_tags_and_collapses_space():
    assert strip_html("<p>use  <b>with</b>\n open()</p>") == "use with open()"

def test_extract_snippet_centers_on_query_term():
    text = "A" * 300 + " usar with open para arquivos " + "B" * 300
    snip = extract_snippet(text, "with open", max_chars=60)
    assert "with open" in snip
    assert len(snip) <= 60 + 1  # tolera reticências

def test_extract_snippet_falls_back_to_start():
    text = "comeco do texto sem o termo procurado aqui"
    snip = extract_snippet(text, "xyzzy", max_chars=20)
    assert snip.startswith("comeco do texto")
    assert len(snip) <= 21

def test_extract_snippet_empty_text():
    assert extract_snippet("", "qualquer") == ""
