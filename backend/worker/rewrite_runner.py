"""Генерация рерайта.

Модель подключается через vsellm (OpenAI-совместимый API); какая именно модель — задаёт
LLM_MODEL в настройках. Без заданного ключа работает заглушка, чтобы сервис оставался
рабочим для демо. Проверка уникальности (Text.ru) — задел на будущее (пока uniqueness=None).
"""
import logging
from typing import Optional

from database.config import get_settings

logger = logging.getLogger(__name__)

# Промпт задаёт tone of voice редакции и требование не выдумывать факты.
# Правится под редакцию; при желании выносится в отдельный конфиг по аналогии с region.yml.
REWRITE_SYSTEM_PROMPT = """Ты — редактор регионального новостного СМИ. Перепиши инфоповод в готовую к публикации заметку.

Правила:
- Пиши на русском, в деловом новостном стиле, без канцелярита и воды.
- НЕ придумывай факты, цифры, имена и цитаты — используй только то, что есть в исходнике. Если данных мало, не додумывай.
- Сохрани все конкретные детали: даты, места, числа, должности, названия.
- Сделай текст уникальным: измени формулировки и структуру, не копируй фразы исходника дословно.
- Начни с сути (кто, что, где, когда), дальше детали.
- Верни только текст заметки, без служебных пометок и пояснений."""


def _stub(title: str, body: str) -> tuple[str, Optional[float]]:
    """Резервная генерация без LLM: компонует заголовок и текст в черновик."""
    title = (title or "").strip().rstrip(".")
    body = (body or "").strip()
    rewritten = f"{title}.\n\n{body}" if body else f"{title}."
    return rewritten, None


def generate_rewrite(title: str, body: str) -> tuple[str, Optional[float]]:
    """Возвращает (текст рерайта, % уникальности).

    Если ключ LLM не задан — заглушка. Иначе вызывает модель через vsellm.
    Ошибка вызова пробрасывается наверх (воркер пометит задачу статусом error).
    """
    settings = get_settings()
    if not settings.LLM_API_KEY:
        return _stub(title, body)

    from openai import OpenAI

    client = OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Заголовок: {title}\n\nТекст:\n{body}"},
        ],
        temperature=settings.LLM_TEMPERATURE,
    )
    text = response.choices[0].message.content or ""
    logger.info("Рерайт получен от модели %s, %d символов", settings.LLM_MODEL, len(text))
    return text, None
