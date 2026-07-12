"""CRUD инфоповодов. Обслуживает сбор, гео-фильтр, дедуп, скоринг и ленту редактора."""
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models.item import Item


def create_item(item: Item, session: Session) -> Item:
    session.add(item)
    try:
        session.commit()
    except IntegrityError:
        # url уникален: параллельный прогон сбора (ручной × автосбор) мог вставить его первым.
        # Откатываемся и возвращаем уже существующую запись — вставка идемпотентна, без 500.
        session.rollback()
        existing = get_item_by_url(item.url, session)
        if existing is not None:
            return existing
        raise
    session.refresh(item)
    return item


def get_item(item_id: int, session: Session) -> Optional[Item]:
    return session.get(Item, item_id)


def get_item_by_url(url: str, session: Session) -> Optional[Item]:
    """Проверка на повторный сбор: url уникален."""
    return session.exec(select(Item).where(Item.url == url)).first()


def save_item(item: Item, session: Session) -> Item:
    """Сохранить изменения инфоповода (после гео-фильтра/дедупа/скоринга)."""
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def list_items(
    session: Session,
    status: Optional[str] = None,
    region_relevant: Optional[bool] = None,
    order_by_score: bool = False,
    limit: int = 100,
) -> list[Item]:
    """Выборка инфоповодов. Для ленты редактора — order_by_score по убыванию вероятности."""
    stmt = select(Item)
    if status is not None:
        stmt = stmt.where(Item.status == status)
    if region_relevant is not None:
        stmt = stmt.where(Item.region_relevant.is_(region_relevant))
    if order_by_score:
        stmt = stmt.order_by(Item.score_proba.desc())
    stmt = stmt.limit(limit)
    return list(session.exec(stmt))
