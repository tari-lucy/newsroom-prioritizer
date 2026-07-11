"""API рерайта: постановка задачи в очередь и опрос её статуса/результата."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pika.exceptions import AMQPConnectionError
from sqlmodel import Session

from database.database import get_session
from models.rewrite import Rewrite, RewriteStatus
from queue_client.publisher import publish_rewrite_task
from schemas.rewrite import RefineRequest, RewriteAccepted, RewriteRead, TextInput
from services.crud.item import get_item
from services.crud.rewrite import create_rewrite, get_latest_rewrite_for_item, save_rewrite
from worker.factcheck import check_facts
from worker.rewrite_runner import refine_rewrite
from worker.uniqueness import check_uniqueness

rewrite_router = APIRouter(prefix="/rewrite", tags=["Рерайт"])


@rewrite_router.post("/{item_id}", response_model=RewriteAccepted, status_code=202)
def request_rewrite(item_id: int, session: Session = Depends(get_session)):
    """Поставить задачу рерайта инфоповода в очередь (результат готовит воркер)."""
    if get_item(item_id, session) is None:
        raise HTTPException(status_code=404, detail="Инфоповод не найден")

    rewrite = create_rewrite(Rewrite(item_id=item_id), session)  # статус pending
    try:
        publish_rewrite_task(rewrite.id, item_id)
    except AMQPConnectionError:
        rewrite.status = RewriteStatus.ERROR.value
        save_rewrite(rewrite, session)
        raise HTTPException(status_code=503, detail="Очередь задач недоступна, попробуйте позже")

    return RewriteAccepted(rewrite_id=rewrite.id, item_id=item_id, status=rewrite.status)


@rewrite_router.get("/{item_id}", response_model=Optional[RewriteRead])
def get_rewrite_status(item_id: int, session: Session = Depends(get_session)):
    """Последний рерайт инфоповода: статус и текст, если готов. None — если рерайта ещё не было."""
    return get_latest_rewrite_for_item(item_id, session)


@rewrite_router.post("/{item_id}/factcheck")
def factcheck(item_id: int, data: TextInput, session: Session = Depends(get_session)):
    """Сверить переданный (текущий редактируемый) текст с первоисточником через LLM."""
    item = get_item(item_id, session)
    if item is None:
        raise HTTPException(status_code=404, detail="Инфоповод не найден")
    if not data.text.strip():
        raise HTTPException(status_code=400, detail="Пустой текст")
    return {"factcheck": check_facts(item.title, item.body, data.text)}


@rewrite_router.post("/{item_id}/uniqueness")
def uniqueness(item_id: int, data: TextInput, session: Session = Depends(get_session)):
    """Проверить уникальность переданного текста через Text.ru (короткий опрос для интерактива)."""
    if get_item(item_id, session) is None:
        raise HTTPException(status_code=404, detail="Инфоповод не найден")
    return {"uniqueness": check_uniqueness(data.text, attempts=8, interval=5)}


@rewrite_router.post("/{item_id}/refine")
def refine(item_id: int, data: RefineRequest, session: Session = Depends(get_session)):
    """Доработать текущий текст по указанию редактора (LLM). Синхронно — редактор итеративно правит."""
    item = get_item(item_id, session)
    if item is None:
        raise HTTPException(status_code=404, detail="Инфоповод не найден")
    return {"text": refine_rewrite(item.title, item.body, data.text, data.instruction)}
