"""Формирование обучающей выборки из дозревших инфоповодов.

Метка = попал ли инфоповод в топ по просмотрам внутри месяца публикации. Просмотры — это
метка, а не признак: до публикации их нет, и они накапливаются ~месяц. Поэтому учимся только
на инфоповодах старше LABEL_MATURATION_DAYS, для которых метка уже могла созреть.

TODO (интеграция Метрики): подтянуть просмотры по item.url из Яндекс.Метрики и посчитать
относительный топ-20% внутри месяца → классы низкая/средняя/высокая. В сервисе просмотры не
хранятся (не признак), поэтому источник меток — внешняя выгрузка Метрики (есть в проекте).
"""
import logging
from datetime import datetime, timedelta

from sqlmodel import Session, select

from database.config import get_settings
from models.item import Item

logger = logging.getLogger(__name__)


def collect_matured_items(session: Session) -> list[Item]:
    """Инфоповоды, у которых метка уже могла созреть (старше LABEL_MATURATION_DAYS)."""
    cutoff = datetime.utcnow() - timedelta(days=get_settings().LABEL_MATURATION_DAYS)
    stmt = select(Item).where(Item.published_at.is_not(None), Item.published_at <= cutoff)
    return list(session.exec(stmt))


def build_training_frame(session: Session) -> tuple[list[str], list[str], list[str]]:
    """Готовит (тексты, метки, месяцы публикации) для обучения и out-of-time сплита.

    Тексты берём из БД сервиса. Метки — из просмотров Метрики (TODO): пока не подключено,
    поэтому метки пустые и переобучение честно сообщает «недостаточно данных».
    """
    items = collect_matured_items(session)
    texts = [f"{item.title} {item.body}" for item in items]
    months = [item.published_at.strftime("%Y-%m") for item in items]

    # TODO: labels = relative_top20_by_month(views_from_metrika(item.url) ...)
    labels: list[str] = []

    logger.info("Дозревших инфоповодов: %d (метки из Метрики пока не подключены)", len(items))
    return texts, labels, months
