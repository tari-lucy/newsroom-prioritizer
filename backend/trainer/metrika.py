"""Клиент Яндекс.Метрики: суммарные просмотры по URL за период.

Просмотры — это метка «залетел ли инфоповод» (её нельзя знать до публикации). Reporting API
отдаёт pageviews по URLPathFull; агрегируем за период по каждому пути. Пустой токен/счётчик →
пустой результат (петля переобучения честно сообщит «недостаточно данных»).
"""
import logging
import time

import requests

from database.config import get_settings

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 100000


def fetch_views(date1: str, date2: str) -> dict[str, int]:
    """Возвращает {путь_url: суммарные просмотры} за период [date1, date2] (даты ISO)."""
    settings = get_settings()
    if not settings.METRIKA_TOKEN or not settings.METRIKA_COUNTER:
        logger.info("Метрика: нет токена/счётчика — метки не подтягиваются")
        return {}

    views: dict[str, int] = {}
    offset = 1
    try:
        while True:
            params = {
                "ids": settings.METRIKA_COUNTER,
                "metrics": "ym:pv:pageviews",
                "dimensions": "ym:pv:URLPathFull",
                "filters": f"ym:pv:URLPathFull=@'{settings.METRIKA_URL_FILTER}'",
                "date1": date1,
                "date2": date2,
                "accuracy": "full",
                "limit": _PAGE_LIMIT,
                "offset": offset,
            }
            resp = requests.get(
                settings.METRIKA_BASE_URL,
                params=params,
                headers={"Authorization": f"OAuth {settings.METRIKA_TOKEN}"},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            for row in data:
                # Кривую строку пропускаем, а не роняем весь сбор.
                try:
                    path = row["dimensions"][0]["name"]
                    views[path] = views.get(path, 0) + int(row["metrics"][0])
                except (KeyError, IndexError, ValueError, TypeError):
                    continue
            if len(data) < _PAGE_LIMIT:
                break
            offset += _PAGE_LIMIT
            time.sleep(0.3)
    except Exception as e:
        # Любая проблема с Метрикой = метки просто не подтягиваются в этот прогон.
        logger.warning("Метрика недоступна: %s — метки пропускаем", e)
        return {}

    logger.info("Метрика: получено просмотров по %d URL за %s..%s", len(views), date1, date2)
    return views
