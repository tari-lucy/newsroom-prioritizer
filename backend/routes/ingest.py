"""API ручного запуска сбора. Автосбор идёт шедулером; этот эндпоинт — для проверки/по требованию."""
from fastapi import APIRouter, Depends
from sqlmodel import Session

from database.database import get_session
from pipeline.ingest import run_ingest

ingest_router = APIRouter(prefix="/ingest", tags=["Сбор"])


@ingest_router.post("")
def trigger_ingest(session: Session = Depends(get_session)):
    """Прогнать сбор по всем активным источникам и вернуть сводку по результату."""
    return run_ingest(session)
