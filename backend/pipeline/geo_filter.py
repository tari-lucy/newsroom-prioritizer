"""Гео-фильтр релевантности: оставляет только инфоповоды про целевой регион.

Ленты бывают шире по географии, поэтому перед показом редактору отсекаем чужое.
Регион и термины берутся из config/region.yml (не хардкод) по ключу REGION.
Механизм — лексиконный матч по заголовку + тексту (прозрачно и настраиваемо;
апгрейд на NER-гео — задел на будущее).
"""
import logging
from functools import lru_cache

import yaml

from database.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _region_block() -> dict:
    """Читает блок активного региона из region.yml (кэшируется)."""
    settings = get_settings()
    with open(settings.REGION_CONFIG, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    block = data.get(settings.REGION)
    if block is None:
        raise ValueError(f"Регион '{settings.REGION}' не найден в {settings.REGION_CONFIG}")
    logger.info("Гео-фильтр: регион '%s', include-терминов: %d",
                block.get("name", settings.REGION), len(block.get("include", [])))
    return block


def check_region(title: str, body: str) -> tuple[bool, list[str]]:
    """Возвращает (релевантен ли региону, список сработавших терминов).

    Термины в конфиге — основами слов, поэтому сравниваем подстрокой без учёта регистра.
    """
    block = _region_block()
    text = f"{title}\n{body}".lower()
    matched = [term for term in block.get("include", []) if term.lower() in text]
    return bool(matched), matched
