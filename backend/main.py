"""Точка входа REST API сервиса приоритизации инфоповодов."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from database.config import get_settings
from database.database import engine, init_db
# Импорт пакета моделей регистрирует таблицы в метаданных до вызова init_db.
import models  # noqa: F401
from models.source import Source, SourceType
from services.crud.source import create_source, list_sources

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Стартовый набор лент региона — создаётся при первом запуске, дальше правится через UI.
DEFAULT_SOURCES = [
    ("НТС", "https://nts-tv.com/rss/"),
    ("Вести Севастополь", "https://vesti92.ru/rss.xml"),
    ("СТВ", "https://sev.tv/rss.xml"),
    ("РИА Крым", "https://crimea.ria.ru/export/rss2/archive/index.xml"),
]


def seed_sources() -> None:
    """Наполняет БД дефолтными RSS-источниками, если источников ещё нет."""
    if not get_settings().SEED_SOURCES:
        return
    with Session(engine) as session:
        if list_sources(session):
            return
        for name, url in DEFAULT_SOURCES:
            create_source(Source(type=SourceType.RSS.value, name=name, params={"url": url}), session)
        logger.info("Создано %d стартовых источников", len(DEFAULT_SOURCES))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_sources()
    logger.info("API запущен, схема БД готова")
    yield
    logger.info("API остановлен")


app = FastAPI(
    title="Newsroom Prioritizer API",
    description="Приоритизация инфоповодов редакции: сбор → дедуп → скоринг → рерайт",
    version="0.1.0",
    lifespan=lifespan,
)


from routes.sources import sources_router
app.include_router(sources_router)

from routes.ingest import ingest_router
app.include_router(ingest_router)

from routes.feed import feed_router
app.include_router(feed_router)

from routes.rewrite import rewrite_router
app.include_router(rewrite_router)

from routes.feedback import feedback_router
app.include_router(feedback_router)


@app.get("/")
def root():
    return {"service": "newsroom-prioritizer", "docs": "/docs"}


@app.get("/health")
def health():
    """Healthcheck для Docker и nginx: 200, если приложение поднялось."""
    return {"status": "ok"}
