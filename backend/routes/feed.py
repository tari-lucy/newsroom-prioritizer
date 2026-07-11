"""API ленты редактора: свежие инфоповоды сверху, внутри — по вероятности «залетит».

Показываем только инфоповоды от существующих и включённых источников: если ленту удалили
или выключили, её новости из ленты сервиса пропадают (не мешают редактору).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import nulls_last
from sqlmodel import Session, select

from database.database import get_session
from models.item import Item, ItemStatus
from models.source import Source
from schemas.item import ItemRead
from services.crud.feedback import get_feedback_for_item

feed_router = APIRouter(prefix="/feed", tags=["Лента"])


@feed_router.get("", response_model=list[ItemRead])
def get_feed(limit: int = 100, session: Session = Depends(get_session)):
    """Релевантные региону, оценённые инфоповоды активных источников: сорт по дате, затем по вероятности."""
    stmt = (
        select(Item)
        .join(Source, Item.source_id == Source.id)   # только существующие источники
        .where(
            Item.status == ItemStatus.SCORED.value,
            Item.region_relevant.is_(True),
            Source.active.is_(True),                  # и только включённые
        )
        .order_by(nulls_last(Item.published_at.desc()), Item.score_proba.desc())
        .limit(limit)
    )
    items = list(session.exec(stmt))

    # Разворачиваем имя источника и текущую оценку из связей — для отображения в карточке.
    result = []
    for i in items:
        feedbacks = get_feedback_for_item(i.id, session)
        result.append(ItemRead(
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
            feedback=feedbacks[0].verdict if feedbacks else None,
        ))
    return result
