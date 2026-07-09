"""Подключение к БД: движок, сессии, инициализация схемы."""
from sqlmodel import Session, SQLModel, create_engine

from database.config import get_settings

settings = get_settings()

# pool_pre_ping отсеивает «умершие» соединения — важно при рестартах контейнера БД.
engine = create_engine(
    settings.database_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
)


def get_session():
    """Зависимость FastAPI: сессия БД на время одного запроса."""
    with Session(engine) as session:
        yield session


def init_db() -> None:
    """Создаёт таблицы по описанным SQLModel-моделям (идемпотентно)."""
    SQLModel.metadata.create_all(engine)
