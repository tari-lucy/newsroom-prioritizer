"""Проверка уникальности текста через Text.ru (асинхронный API).

Протокол: отправляем текст (получаем uid) → опрашиваем результат (код 181 = ещё проверяется).
Используется как контроль качества рерайта (aux-метрика). Любая ошибка/таймаут не роняет
рерайт — возвращается None. Пустой ключ или короткий текст (<100 символов Text.ru не берёт)
тоже дают None, чтобы не тратить проверки впустую.
"""
import logging
import time
from typing import Optional

import requests

from database.config import get_settings

logger = logging.getLogger(__name__)

MIN_CHARS = 100
NOT_READY_CODE = "181"


def check_uniqueness(text: str, attempts: Optional[int] = None, interval: Optional[int] = None) -> Optional[float]:
    """Возвращает процент уникальности (0–100) или None, если проверка недоступна/не удалась.

    attempts/interval переопределяют опрос (для интерактивной проверки — короче, чем в воркере).
    """
    settings = get_settings()
    if not settings.TEXTRU_API_KEY:
        return None
    if len(text) < MIN_CHARS:
        logger.info("Текст короче %d символов — уникальность не проверяем", MIN_CHARS)
        return None
    attempts = attempts or settings.TEXTRU_POLL_ATTEMPTS
    interval = interval or settings.TEXTRU_POLL_INTERVAL

    try:
        # Шаг 1: отправляем текст на проверку, получаем идентификатор.
        submit = requests.post(
            settings.TEXTRU_BASE_URL,
            data={"text": text, "userkey": settings.TEXTRU_API_KEY},
            timeout=30,
        )
        submit.raise_for_status()
        uid = submit.json().get("text_uid")
        if not uid:
            logger.warning("Text.ru не принял текст: %s", submit.json().get("error_desc"))
            return None

        # Шаг 2: опрашиваем результат, пока проверка не завершится.
        for _ in range(attempts):
            time.sleep(interval)
            poll = requests.post(
                settings.TEXTRU_BASE_URL,
                data={"uid": uid, "userkey": settings.TEXTRU_API_KEY},
                timeout=30,
            )
            poll.raise_for_status()
            result = poll.json()
            if str(result.get("error_code")) == NOT_READY_CODE:
                continue
            unique = result.get("text_unique")
            if unique is not None:
                return round(float(unique), 2)
            logger.warning("Text.ru вернул ошибку: %s", result.get("error_desc"))
            return None

        logger.warning("Text.ru: результат не готов за отведённое время")
        return None
    except Exception as e:
        logger.warning("Ошибка проверки уникальности: %s", e)
        return None
