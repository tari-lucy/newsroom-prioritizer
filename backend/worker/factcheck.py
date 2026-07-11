"""Фактчек рерайта: LLM сверяет переписанный текст с исходником и указывает расхождения фактов.

Без ключа LLM возвращает None (фактчек недоступен). Промпт вынесен отдельной константой —
его удобно дорабатывать под редакцию.
"""
import logging
from typing import Optional

from database.config import get_settings

logger = logging.getLogger(__name__)

# Промпт фактчекера. Правится под требования редакции.
FACTCHECK_PROMPT = """Ты — фактчекер новостной редакции. Сравни ПЕРЕПИСАННЫЙ текст с ИСХОДНЫМ и проверь, не исказились ли факты.

Правила:
- Проверяй только фактическую точность: имена, должности, числа, даты, места, цитаты, суть событий.
- Стиль и красоту НЕ оценивай.
- Если факты сохранены — ответь ровно одной строкой: «✅ Факты сохранены».
- Если есть расхождения — перечисли их кратким списком в формате «было → стало».
- Не выдумывай проблемы там, где их нет. Отвечай по-русски, коротко."""


def check_facts(title: str, body: str, rewrite: str) -> Optional[str]:
    """Возвращает вердикт фактчека или None, если LLM недоступен."""
    settings = get_settings()
    if not settings.LLM_API_KEY:
        return None

    from openai import OpenAI

    client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
    original = f"{title}\n\n{body}".strip()
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": FACTCHECK_PROMPT},
            {"role": "user", "content": f"ИСХОДНЫЙ:\n{original}\n\n---\n\nПЕРЕПИСАННЫЙ:\n{rewrite}"},
        ],
        temperature=0.0,
    )
    verdict = (response.choices[0].message.content or "").strip()
    return verdict or None
