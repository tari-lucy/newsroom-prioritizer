"""Коннектор пабликов ВКонтакте через VK API (wall.get).

Читает стену паблика по его короткому имени (domain). Требует сервисный токен приложения
dev.vk.com (VK_TOKEN); без токена источник просто пропускается. Посты без текста (только фото)
отбрасываются, для репостов берётся текст оригинала.
"""
import logging
from datetime import datetime

import requests

from database.config import get_settings
from pipeline.connectors.base import Connector, RawItem

logger = logging.getLogger(__name__)

VK_API_URL = "https://api.vk.com/method/wall.get"


class VkConnector(Connector):
    def fetch(self, source) -> list[RawItem]:
        settings = get_settings()
        if not settings.VK_TOKEN:
            logger.warning("VK_TOKEN не задан — источник '%s' пропущен", source.name)
            return []

        domain = self._domain(source.params)
        if not domain:
            logger.warning("Источник '%s' без имени паблика (domain/url) — пропуск", source.name)
            return []

        try:
            resp = requests.get(VK_API_URL, params={
                "domain": domain,
                "count": settings.VK_POST_COUNT,
                "access_token": settings.VK_TOKEN,
                "v": settings.VK_API_VERSION,
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("VK API недоступен для '%s': %s", source.name, e)
            return []

        if "error" in data:
            logger.warning("VK API ошибка для '%s': %s", source.name, data["error"].get("error_msg"))
            return []

        items: list[RawItem] = []
        for post in data.get("response", {}).get("items", []):
            text = self._post_text(post)
            if not text:
                continue   # пост без текста (только фото/видео) — не инфоповод
            owner_id, post_id = post.get("owner_id"), post.get("id")
            url = f"https://vk.com/wall{owner_id}_{post_id}"
            published_at = datetime.fromtimestamp(post["date"]) if post.get("date") else None
            items.append(RawItem(url=url, title=text.split("\n")[0][:120], body=text, published_at=published_at))

        logger.info("Паблик ВК '%s': получено %d постов", source.name, len(items))
        return items

    @staticmethod
    def _domain(params: dict) -> str:
        """Имя паблика из params: domain, либо извлекаем из ссылки vk.com/xxx."""
        value = (params.get("domain") or params.get("url") or "").strip().rstrip("/")
        if "vk.com/" in value:
            value = value.split("vk.com/")[-1]
        return value.split("/")[0].split("?")[0]

    @staticmethod
    def _post_text(post: dict) -> str:
        """Текст поста; для репоста без своего текста берём текст оригинала."""
        text = (post.get("text") or "").strip()
        if not text:
            for repost in post.get("copy_history", []):
                reposted = (repost.get("text") or "").strip()
                if reposted:
                    return reposted
        return text
