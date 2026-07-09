"""Точка входа REST API сервиса приоритизации инфоповодов."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.database import init_db
# Импорт пакета моделей регистрирует таблицы в метаданных до вызова init_db.
import models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # На старте поднимаем схему БД. Модели данных добавляются на следующем шаге.
    init_db()
    logger.info("API запущен, схема БД готова")
    yield
    logger.info("API остановлен")


app = FastAPI(
    title="Newsroom Prioritizer API",
    description="Приоритизация инфоповодов редакции: сбор → дедуп → скоринг → рерайт",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {"service": "newsroom-prioritizer", "docs": "/docs"}


@app.get("/health")
def health():
    """Healthcheck для Docker и nginx: 200, если приложение поднялось."""
    return {"status": "ok"}
