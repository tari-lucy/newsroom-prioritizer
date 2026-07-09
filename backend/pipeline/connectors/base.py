"""Абстракция источника. Новый тип (соцсеть/мессенджер) = новый класс-коннектор,
пайплайн (гео-фильтр/дедуп/скоринг/UI) при этом не меняется."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RawItem:
    """Сырой инфоповод от коннектора, приведённый к единому виду."""
    url: str
    title: str
    body: str = ""
    published_at: Optional[datetime] = None


class Connector(ABC):
    """Интерфейс коннектора. Реализация читает свой источник и отдаёт список RawItem."""

    @abstractmethod
    def fetch(self, source) -> list[RawItem]:
        """Прочитать источник `source` (модель Source) и вернуть свежие инфоповоды."""
        raise NotImplementedError
