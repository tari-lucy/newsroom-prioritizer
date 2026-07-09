"""API обратной связи редактора (👍/👎). Оценки копятся как ML-сигнал для дообучения."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from database.database import get_session
from models.feedback import FeedbackVerdict
from schemas.feedback import FeedbackCreate, FeedbackExportRow, FeedbackRead
from services.crud.feedback import get_feedback_for_item, list_feedback, upsert_feedback
from services.crud.item import get_item

feedback_router = APIRouter(prefix="/feedback", tags=["Обратная связь"])

VALID_VERDICTS = {v.value for v in FeedbackVerdict}


@feedback_router.post("/{item_id}", response_model=FeedbackRead)
def set_feedback(item_id: int, data: FeedbackCreate, session: Session = Depends(get_session)):
    """Поставить/сменить оценку инфоповода. Повторный клик обновляет запись (upsert)."""
    if data.verdict not in VALID_VERDICTS:
        raise HTTPException(status_code=400, detail=f"verdict должен быть одним из {sorted(VALID_VERDICTS)}")
    if get_item(item_id, session) is None:
        raise HTTPException(status_code=404, detail="Инфоповод не найден")
    return upsert_feedback(item_id, data.verdict, session)


@feedback_router.get("/{item_id}", response_model=Optional[FeedbackRead])
def get_feedback(item_id: int, session: Session = Depends(get_session)):
    """Текущая оценка инфоповода (None — если ещё не оценён)."""
    feedbacks = get_feedback_for_item(item_id, session)
    return feedbacks[0] if feedbacks else None


@feedback_router.get("", response_model=list[FeedbackExportRow])
def export_feedback(session: Session = Depends(get_session)):
    """Выгрузка всех оценок с контекстом инфоповода — для формирования обучающего датасета."""
    rows = []
    for fb in list_feedback(session):
        item = get_item(fb.item_id, session)
        rows.append(FeedbackExportRow(
            item_id=fb.item_id,
            verdict=fb.verdict,
            created_at=fb.created_at,
            title=item.title if item else "",
            score_proba=item.score_proba if item else None,
            score_class=item.score_class if item else None,
        ))
    return rows
