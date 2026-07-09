"""Инфоповод: единица, которая проходит гео-фильтр, дедуп и скоринг."""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, Relationship, SQLModel

from models.source import Source

if TYPE_CHECKING:
    from models.feedback import Feedback
    from models.rewrite import Rewrite


class ItemStatus(str, Enum):
    """Стадия жизненного цикла инфоповода в пайплайне."""
    NEW = "new"                       # только собрано коннектором
    DUPLICATE = "duplicate"           # отсеяно дедупом
    OUT_OF_REGION = "out_of_region"   # не относится к региону
    SCORED = "scored"                 # прошло фильтры, оценено, видно редактору


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: Optional[int] = Field(default=None, foreign_key="source.id", index=True)

    # url уникален — защищает от повторного сбора одного и того же материала.
    url: str = Field(index=True, unique=True)
    title: str
    body: str = Field(default="", sa_column=Column(Text))
    published_at: Optional[datetime] = Field(default=None, index=True)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    # Дедуп: идентификатор группы дублей (у канонической записи и её дублей совпадает).
    dedup_group: Optional[str] = Field(default=None, index=True)

    # Гео-фильтр: None — ещё не проверялось; список сработавших терминов — для прозрачности.
    region_relevant: Optional[bool] = Field(default=None, index=True)
    matched_terms: list = Field(default_factory=list, sa_column=Column(JSON))

    # Результат скоринга приоритизатора.
    score_proba: Optional[float] = Field(default=None, index=True)
    score_class: Optional[str] = Field(default=None)

    status: str = Field(default=ItemStatus.NEW.value, index=True)

    source: Optional[Source] = Relationship(back_populates="items")
    rewrites: list["Rewrite"] = Relationship(back_populates="item")
    feedbacks: list["Feedback"] = Relationship(back_populates="item")
