"""Фоновый сбор: периодически запускает ingest. Отдельный сервис в docker-compose."""
import logging
import signal
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


class _CycleTimeout(Exception):
    """Цикл сбора превысил жёсткий лимит — прерываем, чтобы шедулер не завис навсегда."""


def _raise_cycle_timeout(signum, frame):
    raise _CycleTimeout


def main() -> None:
    settings = get_settings()
    interval = settings.INGEST_INTERVAL_MINUTES * 60
    cap = settings.INGEST_CYCLE_TIMEOUT
    # SIGALRM прерывает зависший сетевой вызов в главном потоке (сервер, игнорящий read-таймаут):
    # без этого одна «мёртвая» загрузка останавливает автосбор до перезапуска контейнера.
    signal.signal(signal.SIGALRM, _raise_cycle_timeout)
    logger.info("Шедулер запущен, интервал сбора: %d мин, лимит цикла: %d с", settings.INGEST_INTERVAL_MINUTES, cap)

    while True:
        try:
            signal.alarm(cap)
            with Session(engine) as session:
                summary = run_ingest(session)
            logger.info("Автосбор: %s", summary)
        except _CycleTimeout:
            logger.error("Цикл сбора превысил %d с и прерван — следующий по расписанию", cap)
        except Exception as e:  # сбор не должен падать насмерть из-за одной ошибки
            logger.error("Ошибка автосбора: %s", e)
        finally:
            signal.alarm(0)  # снимаем будильник в любом случае
        time.sleep(interval)


if __name__ == "__main__":
    main()
