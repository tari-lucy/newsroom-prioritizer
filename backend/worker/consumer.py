"""Воркер рерайта: читает задачи из очереди, генерирует текст, пишет результат в БД.

Статусы Rewrite: pending → processing → done/error. При ошибке фиксируем error, но
сообщение всё равно подтверждаем (ack), чтобы не крутить «битую» задачу бесконечно.
"""
import json
import logging
import time

import pika
from pika.exceptions import AMQPConnectionError, ConnectionClosedByBroker, StreamLostError
from sqlmodel import Session

from database.config import get_settings
from database.database import engine
from models.rewrite import RewriteStatus
from services.crud.item import get_item
from services.crud.rewrite import get_rewrite, save_rewrite
from worker.rewrite_runner import generate_rewrite
# Импорт моделей нужен для конфигурации маппера вне процесса API.
import models  # noqa: F401

logger = logging.getLogger(__name__)


def _process_message(body: bytes) -> None:
    try:
        message = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        logger.error("Невалидный JSON в сообщении: %s", e)
        return

    rewrite_id = message.get("rewrite_id")
    item_id = message.get("item_id")
    if not isinstance(rewrite_id, int) or not isinstance(item_id, int):
        logger.error("Некорректное сообщение: %s", message)
        return

    with Session(engine) as session:
        rewrite = get_rewrite(rewrite_id, session)
        if rewrite is None:
            logger.error("rewrite_id=%s не найден в БД — пропуск", rewrite_id)
            return
        try:
            rewrite.status = RewriteStatus.PROCESSING.value
            save_rewrite(rewrite, session)

            item = get_item(item_id, session)
            if item is None:
                raise ValueError(f"item_id={item_id} не найден")

            text, uniqueness = generate_rewrite(item.title, item.body)
            rewrite.text = text
            rewrite.uniqueness = uniqueness
            rewrite.status = RewriteStatus.DONE.value
            save_rewrite(rewrite, session)
            logger.info("Рерайт готов: rewrite_id=%s", rewrite_id)
        except Exception as e:
            logger.error("Ошибка рерайта rewrite_id=%s: %s", rewrite_id, e)
            rewrite.status = RewriteStatus.ERROR.value
            save_rewrite(rewrite, session)


def _on_message(channel, method, properties, body: bytes) -> None:
    try:
        _process_message(body)
    except Exception as e:
        logger.error("Неожиданная ошибка обработки: %s", e)
    finally:
        channel.basic_ack(delivery_tag=method.delivery_tag)


def start_worker() -> None:
    settings = get_settings()
    while True:
        try:
            credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
            connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                credentials=credentials,
                heartbeat=600,
            ))
            channel = connection.channel()
            channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)
            # prefetch_count=1: не набирать задачи впрок, пока текущая не обработана.
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=settings.RABBITMQ_QUEUE, on_message_callback=_on_message)
            logger.info("Воркер рерайта запущен, очередь '%s'", settings.RABBITMQ_QUEUE)
            channel.start_consuming()
        except (AMQPConnectionError, StreamLostError, ConnectionClosedByBroker) as e:
            logger.error("Соединение с RabbitMQ потеряно: %s. Переподключение через 5с", e)
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Остановка воркера")
            break


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | worker | %(message)s",
    )
    start_worker()
