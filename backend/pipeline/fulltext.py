"""Извлечение полного текста статьи по ссылке.

RSS отдаёт только анонс, а приоритизатор и дедуп работают лучше на полном тексте (модель
на нём и обучена). cloudscraper проходит защиту ddos-guard (сайт НТС), trafilatura достаёт
основной текст из HTML разных изданий без пер-сайтовых селекторов. Любая ошибка сети/парсинга
не роняет сбор — возвращается None, и пайплайн откатывается на анонс из RSS.
"""
import logging
import threading
from typing import Optional

import cloudscraper
import trafilatura

logger = logging.getLogger(__name__)

# Скрапер — свой на каждый поток: cloudscraper (requests.Session) не потокобезопасен, а дотяг
# идёт параллельно. Пул переиспользует потоки, поэтому обход защиты решается раз на поток.
_local = threading.local()


def _get_scraper():
    scraper = getattr(_local, "scraper", None)
    if scraper is None:
        scraper = cloudscraper.create_scraper()
        _local.scraper = scraper
    return scraper


def fetch_fulltext(url: str, timeout: int = 20) -> Optional[str]:
    """Возвращает полный текст статьи или None (тогда используется анонс из RSS)."""
    try:
        resp = _get_scraper().get(url, timeout=timeout)
        if resp.status_code != 200:
            logger.warning("Полный текст %s: код %s", url, resp.status_code)
            return None
        # trafilatura сам определяет кодировку (в т.ч. windows-1251) из байтов.
        text = trafilatura.extract(resp.content, include_comments=False, favor_precision=True)
        return text.strip() if text else None
    except Exception as e:
        logger.warning("Не удалось получить полный текст %s: %s", url, e)
        return None
