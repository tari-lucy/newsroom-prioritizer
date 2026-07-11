"""Реестр коннекторов: сопоставляет тип источника с его реализацией."""
from typing import Optional

from models.source import SourceType
from pipeline.connectors.base import Connector, RawItem
from pipeline.connectors.rss import RssConnector
from pipeline.connectors.vk import VkConnector

# Расширение на соцсети/мессенджеры — добавлением класса и строки в реестр.
_REGISTRY: dict[str, type[Connector]] = {
    SourceType.RSS.value: RssConnector,
    SourceType.VK.value: VkConnector,
}


def get_connector(source_type: str) -> Optional[Connector]:
    connector_cls = _REGISTRY.get(source_type)
    return connector_cls() if connector_cls else None


__all__ = ["Connector", "RawItem", "get_connector"]
