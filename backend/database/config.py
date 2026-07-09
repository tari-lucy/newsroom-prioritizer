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

    # Пайплайн: гео-фильтр (регион вынесен в настройки, не в код)
    REGION: str = "sevastopol_crimea"          # ключ активного региона в region.yml
    REGION_CONFIG: str = "/config/region.yml"   # путь к файлу с гео-терминами

    # Пайплайн: дедуп и сбор
    # Порог косинуса для «дубль». EDA давал ~0.9 на ПОЛНЫХ текстах статей; RSS отдаёт
    # короткие анонсы, для них порог ниже. Калибруется на реально собранных данных.
    DEDUP_THRESHOLD: float = 0.75
    DEDUP_WINDOW_HOURS: int = 48                # окно, в котором ищем дубли
    INGEST_INTERVAL_MINUTES: int = 30           # период автосбора шедулером

    # Приоритизатор: путь к обученной модели (подключается на шаге 7; пока работает заглушка)
    MODEL_PATH: str = "/config/virality_logreg.joblib"

    # LLM для рерайта — через vsellm (OpenAI-совместимый API).
    # Модель выбирается переменной LLM_MODEL и меняется без правки кода.
    # Пустой LLM_API_KEY -> рерайт работает на заглушке (сервис остаётся рабочим).
    LLM_BASE_URL: str = "https://api.vsellm.ru/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek/deepseek-v3.2"   # точный id — из каталога vsellm (напр. gpt-4o, claude-sonnet-4.6)
    LLM_TEMPERATURE: float = 0.3

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
