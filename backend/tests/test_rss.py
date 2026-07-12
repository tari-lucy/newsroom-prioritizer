"""Тесты RSS-коннектора (сеть замокана)."""
import requests

import pipeline.connectors.rss as rss
from models.source import Source, SourceType

# Байтовый литерал не держит кириллицу — собираем как str и кодируем.
SAMPLE_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>Пожар в Севастополе</title><link>http://site/news/1</link>
<description>Загорелся склад</description></item>
</channel></rss>""".encode("utf-8")


class _Resp:
    content = SAMPLE_FEED


def _source(url):
    return Source(type=SourceType.RSS.value, name="Лента", params={"url": url})


def test_rss_parses_feed(monkeypatch):
    monkeypatch.setattr(rss.requests, "get", lambda *a, **k: _Resp())
    items = rss.RssConnector().fetch(_source("http://site/rss"))
    assert len(items) == 1
    assert items[0].title == "Пожар в Севастополе"
    assert items[0].url == "http://site/news/1"


def test_rss_ssl_fallback(monkeypatch):
    """Битая цепочка сертификата (госсайт) — источник не выпадает, идёт повтор без проверки TLS."""
    calls = {"n": 0}

    def _get(url, headers=None, timeout=None, verify=True):
        calls["n"] += 1
        if verify:
            raise requests.exceptions.SSLError("bad chain")
        return _Resp()

    monkeypatch.setattr(rss.requests, "get", _get)
    items = rss.RssConnector().fetch(_source("https://gov/rss"))
    assert len(items) == 1
    assert calls["n"] == 2   # первый заход с проверкой упал, второй без проверки — успех


def test_rss_no_url():
    assert rss.RssConnector().fetch(_source(None)) == []
