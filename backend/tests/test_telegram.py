"""Тесты коннектора Telegram (HTTP-запрос к t.me/s/ замокан)."""
import pipeline.connectors.telegram as tg
from models.source import Source, SourceType

# Фрагмент превью-виджета t.me/s/: два поста с текстом и один медийный (без js-message_text).
_HTML = """
<html><body>
  <div class="tgme_widget_message js-widget_message" data-post="testchannel/10">
    <div class="tgme_widget_message_text js-message_text" dir="auto">Заголовок поста<br>вторая строка</div>
    <a class="tgme_widget_message_date" href="https://t.me/testchannel/10">
      <time datetime="2024-01-15T10:30:00+00:00" class="time">10:30</time></a>
  </div>
  <div class="tgme_widget_message js-widget_message" data-post="testchannel/11">
    <div class="tgme_widget_message_photo_wrap"></div>
  </div>
  <div class="tgme_widget_message js-widget_message" data-post="testchannel/12">
    <div class="tgme_widget_message_text js-message_text" dir="auto">Другая новость</div>
  </div>
</body></html>
"""


class _Resp:
    def __init__(self, content):
        self.content = content.encode("utf-8")

    def raise_for_status(self):
        pass


def _source(params):
    return Source(type=SourceType.TELEGRAM.value, name="Канал", params=params)


def test_telegram_fetch_maps_posts(monkeypatch):
    monkeypatch.setattr(tg.requests, "get", lambda *a, **k: _Resp(_HTML))

    items = tg.TelegramConnector().fetch(_source({"channel": "testchannel"}))
    assert len(items) == 2   # медийный пост без текста пропущен
    assert items[0].url == "https://t.me/testchannel/10"
    assert items[0].title == "Заголовок поста"
    assert "вторая строка" in items[0].body   # <br> сохранён как перенос
    assert items[0].published_at.year == 2024
    assert items[1].body == "Другая новость"


def test_telegram_no_channel():
    assert tg.TelegramConnector().fetch(_source({})) == []


def test_telegram_request_error(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(tg.requests, "get", _boom)
    assert tg.TelegramConnector().fetch(_source({"channel": "x"})) == []


def test_telegram_channel_extraction():
    ch = tg.TelegramConnector._channel
    assert ch({"channel": "testchannel"}) == "testchannel"
    assert ch({"url": "https://t.me/testchannel"}) == "testchannel"
    assert ch({"url": "https://t.me/s/testchannel/"}) == "testchannel"
    assert ch({"channel": "@testchannel"}) == "testchannel"
