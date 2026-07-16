"""Схемы запросов/ответов для управления источниками через API."""
from datetime import datetime

from pydantic import BaseModel

from models.source import SourceCategory, SourceType


class SourceCreate(BaseModel):
    type: str = SourceType.RSS.value          # как читать: rss/vk/telegram
    category: str = SourceCategory.MEDIA.value  # что за источник: СМИ/официальный/прочее
    name: str
    params: dict = {}        # для rss: {"url": "https://..."}
    active: bool = True


class SourceRead(BaseModel):
    id: int
    type: str
    category: str
    name: str
    params: dict
    active: bool
    added_at: datetime

    model_config = {"from_attributes": True}
