"""Формирование обучающей выборки из дозревших инфоповодов.

Метка = попал ли инфоповод в топ по просмотрам внутри месяца публикации. Просмотры — это
метка, а не признак: до публикации их нет, и они накапливаются ~месяц. Поэтому учимся только
на инфоповодах старше LABEL_MATURATION_DAYS, для которых метка уже могла созреть.

Просмотры берём из Яндекс.Метрики по url инфоповода; метки — относительный топ внутри месяца
(верхние 20% — «высокая», 50–80% — «средняя», ниже — «низкая»), как в исходном моделировании.
"""
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import numpy as np
from sqlmodel import Session, select

from database.config import get_settings
from models.item import Item
from trainer.metrika import fetch_views

logger = logging.getLogger(__name__)


def collect_matured_items(session: Session) -> list[Item]:
    """Инфоповоды, у которых метка уже могла созреть (старше LABEL_MATURATION_DAYS)."""
    cutoff = datetime.utcnow() - timedelta(days=get_settings().LABEL_MATURATION_DAYS)
    stmt = select(Item).where(Item.published_at.is_not(None), Item.published_at <= cutoff)
    return list(session.exec(stmt))


def _relative_labels(views: list[int], months: list[str]) -> list[str]:
    """Относительная разметка внутри каждого месяца: топ-20% высокая, 50–80% средняя, ниже низкая."""
    by_month: dict[str, list[int]] = defaultdict(list)
    for value, month in zip(views, months):
        by_month[month].append(value)
    thresholds = {
        month: (float(np.quantile(vals, 0.5)), float(np.quantile(vals, 0.8)))
        for month, vals in by_month.items()
    }

    labels = []
    for value, month in zip(views, months):
        q50, q80 = thresholds[month]
        if value >= q80:
            labels.append("высокая")
        elif value >= q50:
            labels.append("средняя")
        else:
            labels.append("низкая")
    return labels


def build_training_frame(session: Session) -> tuple[list[str], list[str], list[str]]:
    """Готовит (тексты, метки, месяцы публикации) для обучения и out-of-time сплита."""
    items = collect_matured_items(session)
    if not items:
        logger.info("Нет дозревших инфоповодов для разметки")
        return [], [], []

    # Просмотры тянем за период от самой ранней публикации до сегодня.
    date1 = min(item.published_at for item in items).date().isoformat()
    views_by_path = fetch_views(date1, date.today().isoformat())
    if not views_by_path:
        return [], [], []

    texts, views, months = [], [], []
    for item in items:
        pageviews = views_by_path.get(urlparse(item.url).path)
        if pageviews is None:
            continue   # для этого url Метрика просмотров не дала
        texts.append(f"{item.title} {item.body}")
        views.append(pageviews)
        months.append(item.published_at.strftime("%Y-%m"))

    if not texts:
        logger.info("Ни один дозревший инфоповод не сматчился с просмотрами Метрики")
        return [], [], []

    labels = _relative_labels(views, months)
    logger.info("Размечено %d инфоповодов из %d дозревших", len(texts), len(items))
    return texts, labels, months
