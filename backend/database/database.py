"""Подключение к БД: движок, сессии, инициализация схемы."""
import logging

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from database.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# sqlite (тесты) требует отключить проверку потока; для Postgres — обычные параметры.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# pool_pre_ping отсеивает «умершие» соединения — важно при рестартах контейнера БД.
engine = create_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    connect_args=_connect_args,
)


def get_session():
    """Зависимость FastAPI: сессия БД на время одного запроса."""
    with Session(engine) as session:
        yield session


# Колонки, добавленные к уже существующим таблицам: create_all создаёт только НОВЫЕ таблицы
# и не трогает существующие, поэтому на работающей установке колонка иначе не появится.
# Отдельного инструмента миграций проекту пока не нужно — набор изменений мал и линеен.
_ADDED_COLUMNS = [
    ("source", "category", "VARCHAR NOT NULL DEFAULT 'media'"),
]


def _add_column_sql(table: str, column: str, definition: str) -> str:
    """DDL добавления колонки. IF NOT EXISTS делает повторный запуск безопасным."""
    return f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}"


def _apply_column_migrations() -> None:
    """Идемпотентно добавляет новые колонки существующим таблицам (только Postgres).

    В тестах база sqlite создаётся с нуля, поэтому там колонки уже на месте.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table, column, definition in _ADDED_COLUMNS:
            conn.execute(text(_add_column_sql(table, column, definition)))
    logger.info("Схема БД проверена на актуальность")


def init_db() -> None:
    """Создаёт таблицы по описанным SQLModel-моделям (идемпотентно) и доводит схему."""
    SQLModel.metadata.create_all(engine)
    _apply_column_migrations()
