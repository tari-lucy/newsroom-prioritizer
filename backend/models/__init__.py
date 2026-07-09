"""Модели данных. Импорт пакета регистрирует все таблицы в метаданных SQLModel."""
from models.source import Source, SourceType
from models.item import Item, ItemStatus
from models.rewrite import Rewrite, RewriteStatus
from models.feedback import Feedback, FeedbackVerdict
from models.user import User

__all__ = [
    "Source", "SourceType",
    "Item", "ItemStatus",
    "Rewrite", "RewriteStatus",
    "Feedback", "FeedbackVerdict",
    "User",
]
