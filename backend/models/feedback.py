"""Оценка инфоповода редактором (👍/👎).

Копится как размеченный сигнал для будущего обучения: может служить и меткой
(редакционная важность, которая не сводится к просмотрам), и признаком. Пишется
структурно и с контекстом (какой инфоповод, кто, когда), чтобы джойниться к признакам
инфоповода и выгружаться в обучающий датасет.
"""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.item import Item


class FeedbackVerdict(str, Enum):
    LIKE = "like"        # 👍 редактор считает инфоповод стоящим
    DISLIKE = "dislike"  # 👎 не стоящим


class Feedback(SQLModel, table=True):
    # Одна оценка на пару (инфоповод, редактор); смена мнения — через upsert.
    __table_args__ = (UniqueConstraint("item_id", "editor_id", name="uq_feedback_item_editor"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="item.id", index=True)
    editor_id: Optional[int] = Field(default=None, index=True)   # свяжется с авторизацией позже
    verdict: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    item: Optional["Item"] = Relationship(back_populates="feedbacks")
