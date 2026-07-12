"""Коннектор публичных Telegram-каналов через веб-превью t.me/s/<канал>.

Публичный канал отдаёт последние ~20 постов обычной HTML-страницей — ни токена, ни аккаунта
не нужно. Разбираем виджет-разметку t.me (каждый пост — блок с data-post="канал/123").
Посты без текста (только фото/видео) отбрасываются. Любая ошибка сети/разбора не роняет сбор —
возвращается пустой список.
"""
import logging
from datetime import datetime

import lxml.html
import requests

from pipeline.connectors.base import Connector, RawItem

logger = logging.getLogger(__name__)

TME_PREVIEW_URL = "https://t.me/s/{channel}"
# t.me отдаёт превью-виджет только «браузерному» User-Agent, боту — урезанную страницу.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsroomBot/1.0)"}


class TelegramConnector(Connector):
    def fetch(self, source) -> list[RawItem]:
        channel = self._channel(source.params)
        if not channel:
            logger.warning("Источник '%s' без имени канала (channel/url) — пропуск", source.name)
            return []

        try:
            resp = requests.get(TME_PREVIEW_URL.format(channel=channel), headers=_HEADERS, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("t.me недоступен для '%s': %s", source.name, e)
            return []

        # Форсируем utf-8 (t.me всегда в нём), не полагаясь на угадывание кодировки lxml.
        tree = lxml.html.fromstring(resp.content, parser=lxml.html.HTMLParser(encoding="utf-8"))
        items: list[RawItem] = []
        # Каждый пост — блок с data-post="канал/<id>"; из него же строится ссылка.
        for msg in tree.xpath('//div[@data-post]'):
            text = self._message_text(msg)
            if not text:
                continue   # пост без текста (только медиа) — не инфоповод
            url = "https://t.me/" + msg.get("data-post")
            items.append(RawItem(
                url=url,
                title=text.split("\n")[0][:120],
                body=text,
                published_at=self._published_at(msg),
            ))

        logger.info("Канал Telegram '%s': получено %d постов", source.name, len(items))
        return items

    @staticmethod
    def _channel(params: dict) -> str:
        """Имя канала из params: channel, либо извлекаем из ссылки t.me/xxx (или @xxx)."""
        value = (params.get("channel") or params.get("url") or "").strip().rstrip("/")
        if "t.me/" in value:
            value = value.split("t.me/")[-1]
        value = value.removeprefix("s/").lstrip("@")   # поддержка t.me/s/xxx и @xxx
        return value.split("/")[0].split("?")[0]

    @staticmethod
    def _message_text(msg) -> str:
        """Текст поста; переносы строк сохраняем, вложенную разметку (ссылки, эмодзи) отбрасываем."""
        nodes = msg.xpath('.//div[contains(@class, "js-message_text")]')
        if not nodes:
            return ""
        # <br> в разметке t.me — реальные переносы абзацев; text_content() их теряет.
        for br in nodes[0].xpath(".//br"):
            br.tail = "\n" + (br.tail or "")
        return nodes[0].text_content().strip()

    @staticmethod
    def _published_at(msg) -> datetime | None:
        """Время поста из <time datetime="..."> (UTC) → локальное наивное, как у прочих коннекторов."""
        stamps = msg.xpath('.//time[@datetime]/@datetime')
        if not stamps:
            return None
        try:
            dt = datetime.fromisoformat(stamps[0])
            return datetime.fromtimestamp(dt.timestamp())
        except ValueError:
            return None
