"""Тесты проверки уникальности (Text.ru; сеть замокана)."""
import worker.uniqueness as uq


class _FakeSettings:
    TEXTRU_API_KEY = "key"
    TEXTRU_BASE_URL = "http://text.ru/post"
    TEXTRU_POLL_ATTEMPTS = 3
    TEXTRU_POLL_INTERVAL = 0


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_uniqueness_flow(monkeypatch):
    monkeypatch.setattr(uq, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(uq.time, "sleep", lambda s: None)

    state = {"polls": 0}

    def fake_post(url, data=None, timeout=None):
        if "text" in data:                       # отправка текста
            return _Resp({"text_uid": "UID1"})
        state["polls"] += 1                       # опрос результата
        if state["polls"] == 1:
            return _Resp({"error_code": 181})     # ещё проверяется
        return _Resp({"text_unique": "87.50"})

    monkeypatch.setattr(uq.requests, "post", fake_post)
    assert uq.check_uniqueness("x" * 150) == 87.5


def test_uniqueness_no_key(monkeypatch):
    class _NoKey:
        TEXTRU_API_KEY = ""

    monkeypatch.setattr(uq, "get_settings", lambda: _NoKey())
    assert uq.check_uniqueness("x" * 150) is None


def test_uniqueness_short_text(monkeypatch):
    monkeypatch.setattr(uq, "get_settings", lambda: _FakeSettings())
    assert uq.check_uniqueness("короткий текст") is None
