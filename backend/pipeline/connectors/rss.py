"""Коннектор RSS-лент. Первый и базовый источник инфоповодов."""
import logging
from datetime import datetime
from time import mktime

import feedparser
import requests
import urllib3

from pipeline.connectors.base import Connector, RawItem

logger = logging.getLogger(__name__)

# Ленту забираем сами через requests: у него актуальный CA-бандл (certifi), в отличие от urllib
# внутри feedparser, который спотыкается о неполные цепочки сертификатов госсайтов.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsroomBot/1.0)"}
# Гасим предупреждение о небезопасном запросе: verify=False используется осознанно как фолбэк.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RssConnector(Connector):
    def fetch(self, source) -> list[RawItem]:
        url = source.params.get("url")
        if not url:
            logger.warning("Источник '%s' без url в params — пропуск", source.name)
            return []

        content = self._load(url, source.name)
        if content is None:
            return []

        feed = feedparser.parse(content)
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

    @staticmethod
    def _load(url: str, name: str) -> bytes | None:
        """Байты ленты. При ошибке TLS-сертификата (неполная цепочка у госсайтов) повторяем
        без проверки TLS, чтобы источник не выпадал молча. Любой иной сбой сети → None."""
        try:
            return requests.get(url, headers=_HEADERS, timeout=20).content
        except requests.exceptions.SSLError:
            logger.warning("Лента '%s': ошибка TLS-сертификата, повтор без проверки", name)
            try:
                return requests.get(url, headers=_HEADERS, timeout=20, verify=False).content
            except Exception as e:
                logger.warning("Лента '%s' недоступна: %s", name, e)
                return None
        except Exception as e:
            logger.warning("Лента '%s' недоступна: %s", name, e)
            return None
