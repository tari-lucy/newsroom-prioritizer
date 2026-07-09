"""Общая обвязка тестов: приложение на изолированной sqlite-БД, без внешних зависимостей.

БД подменяется на файловый sqlite (DATABASE_URL), сид дефолтных лент отключён (SEED_SOURCES),
LLM-ключ пуст. Перед каждым тестом схема пересоздаётся — тесты не влияют друг на друга.
"""
import os
import pathlib
import tempfile

CONFIG_PATH = pathlib.Path(__file__).resolve().parents[2] / "config" / "region.yml"
os.environ["REGION_CONFIG"] = str(CONFIG_PATH)
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.NamedTemporaryFile(suffix='.db', delete=False).name}"
os.environ["SEED_SOURCES"] = "false"
os.environ["LLM_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from pipeline.connectors.base import RawItem


class FakeConnector:
    """Коннектор-заглушка: детерминированный набор инфоповодов без обращения к сети.

    Внутри — релевантный региону инфоповод, его почти-дубль, чужой регион и ещё один
    релевантный. Позволяет проверить гео-фильтр, дедуп и скоринг разом.
    """

    def fetch(self, source):
        return [
            RawItem(url="u1", title="Атака БПЛА на Севастополь", body="В Севастополе сбили дрон над бухтой"),
            RawItem(url="u2", title="Погода в Москве", body="В Москве сегодня дождь"),
            RawItem(url="u3", title="Атака БПЛА на Севастополь", body="В Севастополе сбили дрон над бухтой сегодня утром"),
            RawItem(url="u4", title="Ремонт дороги в Ялте", body="В Ялте начали чинить дорогу"),
        ]


@pytest.fixture()
def client():
    import main
    from database.database import engine

    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture()
def fake_connector():
    """Класс коннектора-заглушки — чтобы тесты не импортировали conftest напрямую."""
    return FakeConnector


@pytest.fixture()
def ingested(client, monkeypatch):
    """Клиент с уже собранными через FakeConnector инфоповодами."""
    monkeypatch.setattr("pipeline.ingest.get_connector", lambda source_type: FakeConnector())
    client.post("/sources", json={"type": "rss", "name": "НТС", "params": {}})
    client.post("/ingest")
    return client
