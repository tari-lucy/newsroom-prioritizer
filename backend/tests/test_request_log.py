"""Тесты журнала обращений (middleware)."""
import logging


def test_logs_request_with_status_and_duration(client, caplog):
    with caplog.at_level(logging.INFO, logger="api.access"):
        client.get("/feed")
    records = [r.getMessage() for r in caplog.records if r.name == "api.access"]
    assert any("GET /feed -> 200" in m for m in records)
    assert any("мс" in m for m in records)   # длительность попадает в журнал


def test_logs_editor_from_token(client, caplog):
    client.post("/auth/register", json={"username": "logged", "password": "secret123"})
    token = client.post("/auth/login", data={"username": "logged", "password": "secret123"}).json()["access_token"]

    with caplog.at_level(logging.INFO, logger="api.access"):
        client.get("/feed", headers={"Authorization": f"Bearer {token}"})
    records = [r.getMessage() for r in caplog.records if r.name == "api.access"]
    # По журналу видно, кто именно пришёл; самого токена в записи нет.
    assert any("редактор#" in m for m in records)
    assert all(token not in m for m in records)


def test_anonymous_request_marked(client, caplog):
    with caplog.at_level(logging.INFO, logger="api.access"):
        client.get("/")
    records = [r.getMessage() for r in caplog.records if r.name == "api.access"]
    assert any("аноним" in m for m in records)


def test_healthcheck_not_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="api.access"):
        client.get("/health")
    records = [r.getMessage() for r in caplog.records if r.name == "api.access"]
    assert records == []   # healthcheck каждые 30 сек — не засоряем журнал
