"""Публикация задач рерайта в очередь. API кладёт задачу и сразу отвечает —
медленный рерайт (LLM) выполняется воркером вне HTTP-цикла."""
import json
import logging

import pika

from database.config import get_settings

logger = logging.getLogger(__name__)


def _connection_params() -> pika.ConnectionParameters:
    settings = get_settings()
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
    return pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=600,
    )


def publish_rewrite_task(rewrite_id: int, item_id: int) -> None:
    """Кладёт задачу рерайта в очередь. Бросает исключение, если брокер недоступен."""
    settings = get_settings()
    connection = pika.BlockingConnection(_connection_params())
    try:
        channel = connection.channel()
        # durable-очередь + persistent-сообщение: задача переживёт перезапуск брокера.
        channel.queue_declare(queue=settings.RABBITMQ_QUEUE, durable=True)
        body = json.dumps({"rewrite_id": rewrite_id, "item_id": item_id}).encode("utf-8")
        channel.basic_publish(
            exchange="",
            routing_key=settings.RABBITMQ_QUEUE,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        logger.info("Задача рерайта rewrite_id=%s поставлена в очередь", rewrite_id)
    finally:
        connection.close()
