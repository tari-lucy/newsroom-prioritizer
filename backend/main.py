"""Точка входа REST API сервиса приоритизации инфоповодов."""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlmodel import Session

from auth.authenticate import authenticate
from auth.hash_password import hash_password
from database.config import get_settings
from database.database import engine, init_db
# Импорт пакета моделей регистрирует таблицы в метаданных до вызова init_db.
import models  # noqa: F401
from models.source import Source, SourceType
from models.user import User
from services.crud.source import create_source, list_sources
from services.crud.user import create_user, get_user_by_username

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


def seed_editor() -> None:
    """Создаёт демо-редактора при первом старте (логин editor / пароль editor123)."""
    if not get_settings().SEED_EDITOR:
        return
    with Session(engine) as session:
        if get_user_by_username("editor", session):
            return
        create_user(User(username="editor", hashed_password=hash_password("editor123")), session)
        logger.info("Создан демо-редактор (editor)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_sources()
    seed_editor()
    logger.info("API запущен, схема БД готова")
    yield
    logger.info("API остановлен")


app = FastAPI(
    title="Newsroom Prioritizer API",
    description="Приоритизация инфоповодов редакции: сбор → дедуп → скоринг → рерайт",
    version="0.1.0",
    lifespan=lifespan,
)

# Журнал обращений: кто из редакторов какими разделами пользуется и как быстро отвечает API.
from services.logging.request_log import RequestLogMiddleware
app.add_middleware(RequestLogMiddleware)


# Авторизация открыта; рабочие эндпоинты доступны только с валидным токеном.
from routes.auth import auth_router
app.include_router(auth_router)

# Защита на уровне роутера — все его эндпоинты требуют аутентификации.
protected = [Depends(authenticate)]

from routes.sources import sources_router
app.include_router(sources_router, dependencies=protected)

from routes.ingest import ingest_router
app.include_router(ingest_router, dependencies=protected)

from routes.feed import feed_router
app.include_router(feed_router, dependencies=protected)

from routes.rewrite import rewrite_router
app.include_router(rewrite_router, dependencies=protected)

# feedback защищён внутри роута — там id редактора берётся из токена.
from routes.feedback import feedback_router
app.include_router(feedback_router)


@app.get("/")
def root():
    return {"service": "newsroom-prioritizer", "docs": "/docs"}


@app.get("/health")
def health():
    """Healthcheck для Docker и nginx: 200, если приложение поднялось."""
    return {"status": "ok"}
