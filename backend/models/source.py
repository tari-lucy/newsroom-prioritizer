"""Источник инфоповодов. Управляется через UI; тип задаёт коннектор для опроса."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.item import Item


class SourceType(str, Enum):
    """Тип источника определяет, какой коннектор его читает."""
    RSS = "rss"
    TELEGRAM = "telegram"   # задел на будущее
    VK = "vk"               # задел на будущее


class Source(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(default=SourceType.RSS.value, index=True)
    name: str
    # Параметры коннектора в свободной форме: для rss — {"url": "..."},
    # для соцсетей/мессенджеров — идентификатор канала, ссылка на креды и т.п.
    params: dict = Field(default_factory=dict, sa_column=Column(JSON))
    active: bool = Field(default=True, index=True)
    added_at: datetime = Field(default_factory=datetime.utcnow)

    items: list["Item"] = Relationship(back_populates="source")
