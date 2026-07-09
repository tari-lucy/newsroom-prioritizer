"""CRUD источников. Источники добавляются/выключаются через UI, поэтому нужен полный набор операций."""
from typing import Optional

from sqlmodel import Session, select

from models.source import Source


def create_source(source: Source, session: Session) -> Source:
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def get_source(source_id: int, session: Session) -> Optional[Source]:
    return session.get(Source, source_id)


def list_sources(session: Session, active_only: bool = False) -> list[Source]:
    stmt = select(Source)
    if active_only:
        stmt = stmt.where(Source.active.is_(True))
    return list(session.exec(stmt))


def set_source_active(source_id: int, active: bool, session: Session) -> Optional[Source]:
    """Включить/выключить источник — без удаления, чтобы не терять историю сбора."""
    source = session.get(Source, source_id)
    if source is None:
        return None
    source.active = active
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def delete_source(source_id: int, session: Session) -> bool:
    source = session.get(Source, source_id)
    if source is None:
        return False
    session.delete(source)
    session.commit()
    return True
