"""Рерайт инфоповода под стиль редакции. Генерируется воркером из очереди (медленный LLM)."""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, Relationship, SQLModel


class RewriteStatus(str, Enum):
    """Стадия обработки задачи рерайта (задача идёт через очередь)."""
    PENDING = "pending"         # поставлено в очередь
    PROCESSING = "processing"   # воркер взял в работу
    DONE = "done"               # готово
    ERROR = "error"             # упало, текст не получен


class Rewrite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True)

    text: Optional[str] = Field(default=None, sa_column=Column(Text))
    uniqueness: Optional[float] = Field(default=None)   # % уникальности (Text.ru), контроль качества
    status: str = Field(default=RewriteStatus.PENDING.value, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    item: Optional["Item"] = Relationship(back_populates="rewrites")
