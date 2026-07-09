"""API ленты редактора: инфоповоды, прошедшие фильтры, по убыванию вероятности «залетит»."""
from fastapi import APIRouter, Depends
from sqlmodel import Session

from database.database import get_session
from models.item import ItemStatus
from schemas.item import ItemRead
from services.crud.item import list_items

feed_router = APIRouter(prefix="/feed", tags=["Лента"])


@feed_router.get("", response_model=list[ItemRead])
def get_feed(limit: int = 100, session: Session = Depends(get_session)):
    """Показанные редактору инфоповоды: релевантные региону, оценённые, сорт по вероятности."""
    items = list_items(
        session,
        status=ItemStatus.SCORED.value,
        region_relevant=True,
        order_by_score=True,
        limit=limit,
    )
    # Разворачиваем имя источника из связи — для отображения в карточке.
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
        )
        for i in items
    ]
