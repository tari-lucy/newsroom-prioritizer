"""CRUD рерайтов. Создаётся при постановке задачи, обновляется воркером."""
from typing import Optional

from sqlmodel import Session, select

from models.rewrite import Rewrite


def create_rewrite(rewrite: Rewrite, session: Session) -> Rewrite:
    session.add(rewrite)
    session.commit()
    session.refresh(rewrite)
    return rewrite


def get_rewrite(rewrite_id: int, session: Session) -> Optional[Rewrite]:
    return session.get(Rewrite, rewrite_id)


def get_latest_rewrite_for_item(item_id: int, session: Session) -> Optional[Rewrite]:
    """Последний рерайт по инфоповоду — его и показываем/опрашиваем на статус."""
    stmt = (
        select(Rewrite)
        .where(Rewrite.item_id == item_id)
        .order_by(Rewrite.created_at.desc())
    )
    return session.exec(stmt).first()


def save_rewrite(rewrite: Rewrite, session: Session) -> Rewrite:
    session.add(rewrite)
    session.commit()
    session.refresh(rewrite)
    return rewrite
