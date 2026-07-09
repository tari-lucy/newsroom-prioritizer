"""Коннектор RSS-лент. Первый и базовый источник инфоповодов."""
import logging
from datetime import datetime
from time import mktime

import feedparser

from pipeline.connectors.base import Connector, RawItem

logger = logging.getLogger(__name__)


class RssConnector(Connector):
    def fetch(self, source) -> list[RawItem]:
        url = source.params.get("url")
        if not url:
            logger.warning("Источник '%s' без url в params — пропуск", source.name)
            return []

        feed = feedparser.parse(url)
        if feed.bozo:
            # Лента может отдать некорректный XML — не роняем сбор, просто логируем.
            logger.warning("Проблема разбора ленты '%s': %s", source.name, feed.bozo_exception)

        items: list[RawItem] = []
        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                continue
            title = (entry.get("title") or "").strip()
            # В RSS обычно только анонс; полный текст добирается скрапингом позже (задел).
            body = (entry.get("summary") or "").strip()

            published_at = None
            if entry.get("published_parsed"):
                published_at = datetime.fromtimestamp(mktime(entry.published_parsed))

            items.append(RawItem(url=link, title=title, body=body, published_at=published_at))

        logger.info("Источник '%s': получено %d записей", source.name, len(items))
        return items
