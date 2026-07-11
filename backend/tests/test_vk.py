"""Тесты коннектора ВК (VK API замокан)."""
import pipeline.connectors.vk as vk
from models.source import Source, SourceType


class _Settings:
    VK_TOKEN = "token"
    VK_API_VERSION = "5.199"
    VK_POST_COUNT = 50


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _source(params):
    return Source(type=SourceType.VK.value, name="Паблик", params=params)


def test_vk_fetch_maps_posts(monkeypatch):
    monkeypatch.setattr(vk, "get_settings", lambda: _Settings())
    payload = {"response": {"items": [
        {"owner_id": -100, "id": 5, "date": 1_700_000_000, "text": "Заголовок поста\nтекст новости"},
        {"owner_id": -100, "id": 6, "date": 1_700_000_100, "text": ""},  # без текста — пропуск
        {"owner_id": -100, "id": 7, "date": 1_700_000_200, "text": "",
         "copy_history": [{"text": "Текст репоста"}]},  # репост — берём оригинал
    ]}}
    monkeypatch.setattr(vk.requests, "get", lambda *a, **k: _Resp(payload))

    items = vk.VkConnector().fetch(_source({"domain": "public_name"}))
    assert len(items) == 2
    assert items[0].url == "https://vk.com/wall-100_5"
    assert items[0].title == "Заголовок поста"
    assert items[1].body == "Текст репоста"


def test_vk_no_token(monkeypatch):
    class _NoToken:
        VK_TOKEN = ""

    monkeypatch.setattr(vk, "get_settings", lambda: _NoToken())
    assert vk.VkConnector().fetch(_source({"domain": "x"})) == []


def test_vk_api_error(monkeypatch):
    monkeypatch.setattr(vk, "get_settings", lambda: _Settings())
    monkeypatch.setattr(vk.requests, "get", lambda *a, **k: _Resp({"error": {"error_msg": "access denied"}}))
    assert vk.VkConnector().fetch(_source({"domain": "x"})) == []


def test_vk_domain_from_url():
    assert vk.VkConnector._domain({"url": "https://vk.com/sevastopol/"}) == "sevastopol"
    assert vk.VkConnector._domain({"domain": "public_name"}) == "public_name"
