"""Фоновый сбор: периодически запускает ingest. Отдельный сервис в docker-compose."""
import logging
import time

from sqlmodel import Session

from database.config import get_settings
from database.database import engine
from pipeline.ingest import run_ingest

# Импорт моделей нужен для корректной конфигурации маппера при работе вне API.
import models  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | scheduler | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    interval = settings.INGEST_INTERVAL_MINUTES * 60
    logger.info("Шедулер запущен, интервал сбора: %d мин", settings.INGEST_INTERVAL_MINUTES)

    while True:
        try:
            with Session(engine) as session:
                summary = run_ingest(session)
            logger.info("Автосбор: %s", summary)
        except Exception as e:  # сбор не должен падать насмерть из-за одной ошибки
            logger.error("Ошибка автосбора: %s", e)
        time.sleep(interval)


if __name__ == "__main__":
    main()
