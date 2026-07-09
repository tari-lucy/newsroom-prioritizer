"""Генерация рерайта. Сейчас заглушка; на этапе расширения (C) заменяется на LLM
(LoRA под tone of voice редакции) + проверку уникальности через Text.ru."""
from typing import Optional


def generate_rewrite(title: str, body: str) -> tuple[str, Optional[float]]:
    """Возвращает (текст рерайта, % уникальности).

    Заглушка компонует заголовок и текст в единый черновик; уникальность пока не считается
    (None). Точка подключения реального LLM и Text.ru — здесь, интерфейс при этом не меняется.
    """
    title = (title or "").strip().rstrip(".")
    body = (body or "").strip()
    rewritten = f"{title}.\n\n{body}" if body else f"{title}."
    uniqueness = None
    return rewritten, uniqueness
