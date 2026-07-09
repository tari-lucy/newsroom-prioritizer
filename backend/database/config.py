"""Конфигурация приложения из переменных окружения (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # База данных
    DB_HOST: str = "database"
    DB_PORT: int = 5432
    DB_USER: str = "newsroom"
    DB_PASS: str = "newsroom"
    DB_NAME: str = "newsroom"

    # Очередь задач
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "newsroom"
    RABBITMQ_PASSWORD: str = "newsroom"
    RABBITMQ_QUEUE: str = "rewrite_tasks"

    # Приложение
    DEBUG: bool = False

    @property
    def database_url(self) -> str:
        """Строка подключения SQLAlchemy к PostgreSQL."""
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Единый кэшированный экземпляр настроек на всё приложение."""
    return Settings()
