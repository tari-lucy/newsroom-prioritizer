"""Учётная запись редактора для входа в сервис."""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.feedback import Feedback


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Оценки редактора: обучающий сигнал копится именно за тем, кто его поставил.
    feedbacks: list["Feedback"] = Relationship(back_populates="editor")
