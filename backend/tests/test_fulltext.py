"""Тесты извлечения полного текста (сеть замокана)."""
import pipeline.fulltext as fulltext

SAMPLE_HTML = """
<html><head><title>Test</title></head><body>
<article>
<h1>Пожар в Ялте</h1>
<p>В Ялте вечером загорелся складской ангар на набережной. По предварительным данным,
огонь охватил площадь около трёхсот квадратных метров.</p>
<p>На место выехали пожарные расчёты. Пострадавших нет, жителей соседних домов
эвакуировали в качестве меры предосторожности.</p>
</article>
</body></html>
""".encode("utf-8")


class _Resp:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


def test_extracts_main_text(monkeypatch):
    monkeypatch.setattr(fulltext._scraper, "get", lambda url, timeout=20: _Resp(200, SAMPLE_HTML))
    text = fulltext.fetch_fulltext("http://example/news/1")
    assert text is not None
    assert "складской ангар" in text
    # Служебные элементы (title/заголовок) в основной текст не тянутся как мусор.
    assert "загорелся" in text


def test_returns_none_on_error(monkeypatch):
    def _boom(url, timeout=20):
        raise ConnectionError("network down")

    monkeypatch.setattr(fulltext._scraper, "get", _boom)
    assert fulltext.fetch_fulltext("http://example/news/1") is None


def test_returns_none_on_bad_status(monkeypatch):
    monkeypatch.setattr(fulltext._scraper, "get", lambda url, timeout=20: _Resp(403, b""))
    assert fulltext.fetch_fulltext("http://example/news/1") is None
