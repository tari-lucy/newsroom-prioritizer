"""Схемы обратной связи редактора."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    verdict: str   # like | dislike


class FeedbackRead(BaseModel):
    id: int
    item_id: int
    editor_id: Optional[int] = None
    verdict: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackExportRow(BaseModel):
    """Строка выгрузки оценок с контекстом инфоповода — заготовка обучающего датасета."""
    item_id: int
    verdict: str
    created_at: datetime
    title: str
    score_proba: Optional[float] = None
    score_class: Optional[str] = None
