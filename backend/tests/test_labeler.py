"""Тесты разметки из Метрики (сеть замокана)."""
from datetime import datetime, timedelta

import trainer.labeler as labeler
import trainer.metrika as metrika
from models.item import Item
from services.crud.item import create_item


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_views_aggregates(monkeypatch):
    class _Settings:
        METRIKA_TOKEN = "t"
        METRIKA_COUNTER = "1"
        METRIKA_BASE_URL = "http://m"
        METRIKA_URL_FILTER = "/news/"

    monkeypatch.setattr(metrika, "get_settings", lambda: _Settings())
    payload = {"data": [
        {"dimensions": [{"name": "/news/1/"}], "metrics": [100]},
        {"dimensions": [{"name": "/news/2/"}], "metrics": [5]},
    ]}
    monkeypatch.setattr(metrika.requests, "get", lambda *a, **k: _Resp(payload))
    views = metrika.fetch_views("2026-01-01", "2026-02-01")
    assert views == {"/news/1/": 100, "/news/2/": 5}


def test_fetch_views_no_token(monkeypatch):
    class _NoKey:
        METRIKA_TOKEN = ""
        METRIKA_COUNTER = ""

    monkeypatch.setattr(metrika, "get_settings", lambda: _NoKey())
    assert metrika.fetch_views("2026-01-01", "2026-02-01") == {}


def test_fetch_views_survives_network_error(monkeypatch):
    class _Settings:
        METRIKA_TOKEN = "t"
        METRIKA_COUNTER = "1"
        METRIKA_BASE_URL = "http://m"
        METRIKA_URL_FILTER = "/news/"

    monkeypatch.setattr(metrika, "get_settings", lambda: _Settings())

    def boom(*a, **k):
        raise ConnectionError("сеть недоступна")

    monkeypatch.setattr(metrika.requests, "get", boom)
    assert metrika.fetch_views("2026-01-01", "2026-02-01") == {}


def test_relative_labels_top20_is_high():
    # 10 инфоповодов одного месяца; максимальный по просмотрам должен стать «высокая».
    views = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    months = ["2026-01"] * 10
    labels = labeler._relative_labels(views, months)
    assert labels[-1] == "высокая"          # топ по просмотрам
    assert labels[0] == "низкая"             # низ распределения


def test_build_training_frame_labels_matured(client, monkeypatch):
    from database.database import engine
    from sqlmodel import Session

    old = datetime.utcnow() - timedelta(days=60)   # старше LABEL_MATURATION_DAYS
    with Session(engine) as session:
        for i in range(4):
            create_item(Item(url=f"http://nts/news/{i}/", title=f"Инфоповод {i}",
                             body="текст", published_at=old), session)

    monkeypatch.setattr(labeler, "fetch_views", lambda d1, d2: {
        "/news/0/": 500, "/news/1/": 3, "/news/2/": 50, "/news/3/": 5,
    })

    with Session(engine) as session:
        texts, labels, months = labeler.build_training_frame(session)

    assert len(texts) == 4
    assert set(labels) <= {"низкая", "средняя", "высокая"}
    assert "высокая" in labels          # самый просматриваемый размечен
