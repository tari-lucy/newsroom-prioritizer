"""Схемы запроса и статуса рерайта."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RewriteAccepted(BaseModel):
    """Ответ на постановку задачи рерайта в очередь."""
    rewrite_id: int
    item_id: int
    status: str


class TextInput(BaseModel):
    """Текущий текст статьи для проверок (фактчек, уникальность) на редактируемом варианте."""
    text: str


class RefineRequest(BaseModel):
    """Доработка текущего текста по указанию редактора."""
    text: str
    instruction: str


class RewriteRead(BaseModel):
    id: int
    item_id: int
    text: Optional[str] = None
    uniqueness: Optional[float] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
