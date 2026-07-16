"""API управления источниками: добавить/посмотреть/включить-выключить/удалить ленту."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from database.database import get_session
from models.source import Source, SourceCategory
from schemas.source import SourceCreate, SourceRead
from services.crud.source import (
    create_source,
    delete_source,
    list_sources,
    set_source_active,
    set_source_category,
)

sources_router = APIRouter(prefix="/sources", tags=["Источники"])


@sources_router.post("", response_model=SourceRead, status_code=201)
def add_source(data: SourceCreate, session: Session = Depends(get_session)):
    source = Source(
        type=data.type,
        category=data.category,
        name=data.name,
        params=data.params,
        active=data.active,
    )
    return create_source(source, session)


@sources_router.get("", response_model=list[SourceRead])
def get_sources(active_only: bool = False, session: Session = Depends(get_session)):
    return list_sources(session, active_only=active_only)


@sources_router.patch("/{source_id}/category", response_model=SourceRead)
def change_source_category(source_id: int, category: SourceCategory, session: Session = Depends(get_session)):
    """Уточнить категорию источника: СМИ / официальный / прочее."""
    source = set_source_category(source_id, category.value, session)
    if source is None:
        raise HTTPException(status_code=404, detail="Источник не найден")
    return source


@sources_router.patch("/{source_id}/active", response_model=SourceRead)
def toggle_source(source_id: int, active: bool, session: Session = Depends(get_session)):
    source = set_source_active(source_id, active, session)
    if source is None:
        raise HTTPException(status_code=404, detail="Источник не найден")
    return source


@sources_router.delete("/{source_id}", status_code=204)
def remove_source(source_id: int, session: Session = Depends(get_session)):
    if not delete_source(source_id, session):
        raise HTTPException(status_code=404, detail="Источник не найден")
