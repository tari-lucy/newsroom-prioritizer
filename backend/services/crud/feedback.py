"""CRUD обратной связи редактора (👍/👎). Одна оценка на пару (инфоповод, редактор) — upsert."""
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from models.feedback import Feedback


def upsert_feedback(
    item_id: int,
    verdict: str,
    session: Session,
    editor_id: Optional[int] = None,
) -> Feedback:
    """Поставить/сменить оценку. Смена мнения обновляет запись, а не плодит дубли."""
    stmt = select(Feedback).where(
        Feedback.item_id == item_id,
        Feedback.editor_id == editor_id,
    )
    feedback = session.exec(stmt).first()
    if feedback is None:
        feedback = Feedback(item_id=item_id, editor_id=editor_id, verdict=verdict)
    else:
        feedback.verdict = verdict
        feedback.created_at = datetime.utcnow()
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return feedback


def get_feedback_for_item(item_id: int, session: Session) -> list[Feedback]:
    return list(session.exec(select(Feedback).where(Feedback.item_id == item_id)))


def list_feedback(session: Session) -> list[Feedback]:
    """Полная выгрузка оценок — для формирования обучающего датасета."""
    return list(session.exec(select(Feedback)))
