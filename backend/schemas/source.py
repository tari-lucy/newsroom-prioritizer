"""Схемы запросов/ответов для управления источниками через API."""
from datetime import datetime

from pydantic import BaseModel

from models.source import SourceType


class SourceCreate(BaseModel):
    type: str = SourceType.RSS.value
    name: str
    params: dict = {}        # для rss: {"url": "https://..."}
    active: bool = True


class SourceRead(BaseModel):
    id: int
    type: str
    name: str
    params: dict
    active: bool
    added_at: datetime

    model_config = {"from_attributes": True}
