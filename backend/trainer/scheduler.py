"""Периодический запуск переобучения. Отдельный сервис в docker-compose."""
import logging
import time

from database.config import get_settings
from trainer.retrain import run_retrain

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | trainer | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    interval = settings.RETRAIN_INTERVAL_DAYS * 24 * 60 * 60
    logger.info("Trainer запущен, период переобучения: %d дн", settings.RETRAIN_INTERVAL_DAYS)

    while True:
        try:
            result = run_retrain()
            logger.info("Переобучение: %s", result)
        except Exception as e:  # переобучение не должно ронять сервис
            logger.error("Ошибка переобучения: %s", e)
        time.sleep(interval)


if __name__ == "__main__":
    main()
