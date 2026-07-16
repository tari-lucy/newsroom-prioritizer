"""API ленты редактора: свежие инфоповоды сверху, внутри — по вероятности «залетит».

Показываем только инфоповоды от существующих и включённых источников: если ленту удалили
или выключили, её новости из ленты сервиса пропадают (не мешают редактору).

Фильтры применяются в запросе к БД, а не к уже загруженной странице: иначе поиск и отбор
по источнику работали бы только по окну свежих записей и «теряли» редко пишущие источники.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlmodel import Session, select

from database.database import get_session
from models.feedback import Feedback
from models.item import Item, ItemStatus
from models.source import Source
from schemas.item import ItemRead

feed_router = APIRouter(prefix="/feed", tags=["Лента"])


@feed_router.get("", response_model=list[ItemRead])
def get_feed(
    limit: int = 200,
    source_id: Optional[int] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    min_proba: Optional[float] = None,
    max_proba: Optional[float] = None,
    days: Optional[int] = None,
    session: Session = Depends(get_session),
):
    """Релевантные региону, оценённые инфоповоды активных источников: сорт по дате, затем по вероятности.

    Необязательные фильтры: источник, категория источника (СМИ/официальный/прочее), подстрока
    в заголовке/тексте, диапазон вероятности «залететь», свежесть в днях. Класс фильтруется
    именно диапазоном вероятности: пороги классов задаёт витрина, здесь — только честное
    сравнение чисел.
    """
    # Дата публикации, а если её нет из RSS — дата сбора (чтобы свежее было сверху всегда).
    freshness = func.coalesce(Item.published_at, Item.ingested_at)
    stmt = (
        select(Item)
        .join(Source, Item.source_id == Source.id)   # только существующие источники
        .where(
            Item.status == ItemStatus.SCORED.value,
            Item.region_relevant.is_(True),
            Source.active.is_(True),                  # и только включённые
        )
    )

    if source_id is not None:
        stmt = stmt.where(Item.source_id == source_id)
    if category:
        stmt = stmt.where(Source.category == category)   # напр. только первоисточники
    if min_proba is not None:
        stmt = stmt.where(Item.score_proba >= min_proba)
    if max_proba is not None:
        stmt = stmt.where(Item.score_proba < max_proba)   # верхняя граница строгая: диапазоны стыкуются
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Item.title.ilike(like), Item.body.ilike(like)))
    if days is not None:
        stmt = stmt.where(freshness >= datetime.utcnow() - timedelta(days=days))

    stmt = stmt.order_by(freshness.desc(), Item.score_proba.desc()).limit(limit)
    items = list(session.exec(stmt))

    # Оценки редактора тянем ОДНИМ запросом на все инфоповоды (без N+1).
    ids = [i.id for i in items]
    verdicts = {}
    if ids:
        for fb in session.exec(select(Feedback).where(Feedback.item_id.in_(ids))):
            verdicts[fb.item_id] = fb.verdict

    return [
        ItemRead(
            id=i.id,
            source_name=i.source.name if i.source else None,
            url=i.url,
            title=i.title,
            body=i.body,
            published_at=i.published_at,
            ingested_at=i.ingested_at,
            score_proba=i.score_proba,
            score_class=i.score_class,
            region_relevant=i.region_relevant,
            matched_terms=i.matched_terms,
            status=i.status,
            feedback=verdicts.get(i.id),
        )
        for i in items
    ]
