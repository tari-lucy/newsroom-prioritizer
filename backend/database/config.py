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
    SEED_SOURCES: bool = True   # создавать дефолтные ленты при первом старте
    SEED_EDITOR: bool = True    # создавать демо-редактора при первом старте

    # Авторизация (JWT)
    SECRET_KEY: str = "dev-secret-change-me"   # в продакшене задать в .env
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_SECONDS: int = 86400            # срок жизни токена (сутки)
    # Переопределение строки подключения (напр. sqlite для тестов). Пусто -> Postgres из DB_*.
    DATABASE_URL: str = ""

    # Пайплайн: гео-фильтр (регион вынесен в настройки, не в код)
    REGION: str = "sevastopol_crimea"          # ключ активного региона в region.yml
    REGION_CONFIG: str = "/config/region.yml"   # путь к файлу с гео-терминами

    # Пайплайн: полный текст статьи. RSS отдаёт только анонс, а модель обучена на полных
    # текстах — перед скорингом дотягиваем тело статьи по ссылке. Отключаемо (напр. в тестах).
    FETCH_FULLTEXT: bool = True

    # Пайплайн: дедуп и сбор
    # Порог косинуса для «дубль». EDA давал ~0.9 на ПОЛНЫХ текстах статей; RSS отдаёт
    # короткие анонсы, для них порог ниже. Калибруется на реально собранных данных.
    DEDUP_THRESHOLD: float = 0.75
    DEDUP_WINDOW_HOURS: int = 48                # окно, в котором ищем дубли
    INGEST_INTERVAL_MINUTES: int = 30           # период автосбора шедулером

    # Приоритизатор: путь к обученной модели. Если файла нет — работает заглушка-эвристика.
    MODEL_PATH: str = "/config/virality_model.joblib"

    # Источник меток для переобучения — Яндекс.Метрика (просмотры = метка «залетело»).
    # Пустой токен -> метки не подтягиваются, петля сообщает «недостаточно данных».
    METRIKA_BASE_URL: str = "https://api-metrika.yandex.net/stat/v1/data"
    METRIKA_TOKEN: str = ""
    METRIKA_COUNTER: str = ""
    METRIKA_URL_FILTER: str = "/news/"   # какие URL считаем инфоповодами

    # Петля переобучения (trainer)
    RETRAIN_INTERVAL_DAYS: int = 30      # период запуска переобучения
    LABEL_MATURATION_DAYS: int = 30      # сколько ждём созревания метки (просмотры набираются)
    RETRAIN_MIN_SAMPLES: int = 200       # минимум размеченных примеров для переобучения
    RETRAIN_GATE_MARGIN: float = 0.0     # кандидат промоутится, если не хуже текущей на эту дельту

    # LLM для рерайта — через vsellm (OpenAI-совместимый API).
    # Модель выбирается переменной LLM_MODEL и меняется без правки кода.
    # Пустой LLM_API_KEY -> рерайт работает на заглушке (сервис остаётся рабочим).
    LLM_BASE_URL: str = "https://api.vsellm.ru/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek/deepseek-v3.2"   # точный id — из каталога vsellm (напр. gpt-4o, claude-sonnet-4.6)
    LLM_TEMPERATURE: float = 0.3

    # Проверка уникальности рерайта через Text.ru (асинхронный API).
    # Пустой ключ -> проверка пропускается (uniqueness остаётся None).
    TEXTRU_BASE_URL: str = "https://api.text.ru/post"
    TEXTRU_API_KEY: str = ""
    TEXTRU_POLL_ATTEMPTS: int = 20   # сколько раз опрашивать результат
    TEXTRU_POLL_INTERVAL: int = 6    # интервал опроса, сек

    @property
    def database_url(self) -> str:
        """Строка подключения SQLAlchemy. DATABASE_URL переопределяет (напр. sqlite в тестах)."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
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
