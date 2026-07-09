"""Схема инфоповода для выдачи в ленту редактора."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ItemRead(BaseModel):
    id: int
    source_name: Optional[str] = None   # имя источника для карточки
    url: str
    title: str
    body: str
    published_at: Optional[datetime] = None
    ingested_at: datetime
    score_proba: Optional[float] = None
    score_class: Optional[str] = None
    region_relevant: Optional[bool] = None
    matched_terms: list = []
    status: str
