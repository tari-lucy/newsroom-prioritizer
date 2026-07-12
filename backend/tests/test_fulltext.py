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


class _Scraper:
    """Заглушка скрапера: get() возвращает заранее заданный ответ или бросает исключение."""
    def __init__(self, handler):
        self._handler = handler

    def get(self, url, timeout=20):
        return self._handler(url, timeout)


def _patch_scraper(monkeypatch, handler):
    # Скрапер теперь thread-local (создаётся через _get_scraper) — мокаем фабрику.
    monkeypatch.setattr(fulltext, "_get_scraper", lambda: _Scraper(handler))


def test_extracts_main_text(monkeypatch):
    _patch_scraper(monkeypatch, lambda url, timeout: _Resp(200, SAMPLE_HTML))
    text = fulltext.fetch_fulltext("http://example/news/1")
    assert text is not None
    assert "складской ангар" in text
    # Служебные элементы (title/заголовок) в основной текст не тянутся как мусор.
    assert "загорелся" in text


def test_returns_none_on_error(monkeypatch):
    def _boom(url, timeout):
        raise ConnectionError("network down")

    _patch_scraper(monkeypatch, _boom)
    assert fulltext.fetch_fulltext("http://example/news/1") is None


def test_returns_none_on_bad_status(monkeypatch):
    _patch_scraper(monkeypatch, lambda url, timeout: _Resp(403, b""))
    assert fulltext.fetch_fulltext("http://example/news/1") is None


def test_ssl_fallback(monkeypatch):
    """Битая цепочка сертификата (напр. sev.gov.ru) — повтор без проверки TLS, текст извлекается."""
    import requests

    class _SSLScraper:
        calls = 0

        def get(self, url, timeout=20, verify=True):
            _SSLScraper.calls += 1
            if verify:
                raise requests.exceptions.SSLError("bad chain")
            return _Resp(200, SAMPLE_HTML)

    monkeypatch.setattr(fulltext, "_get_scraper", lambda: _SSLScraper())
    text = fulltext.fetch_fulltext("https://gov/news/1")
    assert text is not None and "складской ангар" in text
    assert _SSLScraper.calls == 2   # первый заход упал по TLS, второй без проверки — успех
