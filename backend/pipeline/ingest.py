"""Оркестрация сбора: источники → гео-фильтр → дедуп → скоринг → БД.

Один прогон опрашивает активные источники, приводит записи к Item, отсекает чужой регион
и дубли, а прошедшим ставит оценку приоритизатора. Вызывается из API (/ingest) и шедулера.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from sqlmodel import Session, select

from database.config import get_settings
from models.item import Item, ItemStatus
from models.source import SourceType
from pipeline.connectors import get_connector
from pipeline.dedup import best_match
from pipeline.fulltext import fetch_fulltext
from pipeline.geo_filter import check_region
from pipeline.scoring import get_scorer
from services.crud.item import create_item, get_item_by_url, save_item
from services.crud.source import list_sources

logger = logging.getLogger(__name__)


def run_ingest(session: Session) -> dict:
    settings = get_settings()
    summary = {"fetched": 0, "new": 0, "out_of_region": 0, "duplicates": 0}

    # Кандидаты для дедупа — недавние показанные инфоповоды (в окне DEDUP_WINDOW_HOURS).
    window_start = datetime.utcnow() - timedelta(hours=settings.DEDUP_WINDOW_HOURS)
    canon = session.exec(
        select(Item).where(
            Item.status == ItemStatus.SCORED.value,
            Item.ingested_at >= window_start,
        )
    ).all()
    canon_texts = [f"{i.title} {i.body}" for i in canon]
    canon_groups = [i.dedup_group for i in canon]

    scorer = get_scorer()

    # 1. Опрашиваем источники, отсекаем уже собранное (url) и чужой регион.
    #    Релевантные кандидаты откладываем — для них следом параллельно дотянем полный текст.
    to_process: list[tuple] = []   # (source, raw, item) — прошедшие гео-фильтр новинки
    for source in list_sources(session, active_only=True):
        connector = get_connector(source.type)
        if connector is None:
            logger.warning("Нет коннектора для типа '%s' (источник '%s')", source.type, source.name)
            continue

        for raw in connector.fetch(source):
            summary["fetched"] += 1

            # url уникален — уже собранное пропускаем, не перезаписываем.
            if get_item_by_url(raw.url, session):
                continue

            relevant, matched = check_region(raw.title, raw.body)
            item = Item(
                source_id=source.id,
                url=raw.url,
                title=raw.title,
                body=raw.body,
                published_at=raw.published_at,
                region_relevant=relevant,
                matched_terms=matched,
            )

            # Не про регион — сохраняем с пометкой (чтобы не тянуть повторно), но не показываем.
            if not relevant:
                item.status = ItemStatus.OUT_OF_REGION.value
                create_item(item, session)
                summary["out_of_region"] += 1
                continue

            to_process.append((source, raw, item))

    # 2. Полный текст дотягиваем ТОЛЬКО для RSS (анонсы); VK/Telegram отдают текст сразу.
    #    Загрузки идут параллельно с ограниченным таймаутом, чтобы всплеск новинок не растягивал
    #    цикл (при коротком интервале сбора это критично).
    if settings.FETCH_FULLTEXT:
        rss_items = [item for source, raw, item in to_process
                     if source.type == SourceType.RSS.value]
        if rss_items:
            with ThreadPoolExecutor(max_workers=settings.FULLTEXT_WORKERS) as pool:
                futures = {pool.submit(fetch_fulltext, item.url, settings.FULLTEXT_TIMEOUT): item
                           for item in rss_items}
                for future in as_completed(futures):
                    full_text = future.result()
                    if full_text:
                        futures[future].body = full_text

    # 3. Дедуп и скоринг — последовательно, уже на готовом тексте.
    for source, raw, item in to_process:
        text = f"{raw.title} {item.body}"
        idx, sim = best_match(text, canon_texts)
        if sim >= settings.DEDUP_THRESHOLD:
            item.status = ItemStatus.DUPLICATE.value
            item.dedup_group = canon_groups[idx]
            create_item(item, session)
            summary["duplicates"] += 1
            continue

        # Новый инфоповод: скорим и показываем редактору.
        result = scorer.score(raw.title, item.body)
        item.score_proba = result["proba"]
        item.score_class = result["cls"]
        item.status = ItemStatus.SCORED.value
        item = create_item(item, session)
        # dedup_group каноничной записи = её собственный id (дубли будут ссылаться на него).
        item.dedup_group = f"grp-{item.id}"
        save_item(item, session)

        # Пополняем кандидатов, чтобы ловить дубли и внутри одного прогона.
        canon_texts.append(text)
        canon_groups.append(item.dedup_group)
        summary["new"] += 1

    logger.info("Сбор завершён: %s", summary)
    return summary
