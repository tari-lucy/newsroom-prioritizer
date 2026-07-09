"""Приоритизатор «залетит / не залетит» — единая точка подключения модели.

Сейчас работает эвристика-заглушка, чтобы пайплайн был живым без обученной модели.
На шаге 7 в этом же классе заглушка заменяется на загрузку обученного приоритизатора
(virality_logreg.joblib) — остальной сервис (API, витрина) при этом не меняется.
"""
import logging
import os

from database.config import get_settings

logger = logging.getLogger(__name__)


class Scorer:
    CLASSES = ["низкая", "средняя", "высокая"]

    # Эвристические признаки «залетаемости» из редакционных критериев — только для заглушки.
    _BOOSTS = {
        "атак": 0.30, "бпла": 0.30, "дрон": 0.25, "взрыв": 0.25, "пожар": 0.20,
        "погиб": 0.20, "пострадав": 0.15, "дтп": 0.15, "эвакуац": 0.20, "тревог": 0.15,
        "президент": 0.25, "путин": 0.25, "губернатор": 0.15, "развожаев": 0.15,
        "теракт": 0.30, "землетрясен": 0.25, "победа": 0.10,
    }

    def __init__(self):
        self.model = None
        model_path = get_settings().MODEL_PATH
        # Шаг 7: подключение обученной модели ->
        #     import joblib; self.model = joblib.load(model_path)
        if os.path.exists(model_path):
            logger.info("Найден артефакт модели (%s); подключение — на шаге 7", model_path)

    def score(self, title: str, body: str) -> dict:
        """Возвращает {'proba': float, 'cls': str} — вероятность и класс приоритета."""
        if self.model is not None:
            # Шаг 7: реальное предсказание моделью по тексту.
            raise NotImplementedError

        text = f"{title} {body}".lower()
        proba = 0.15 + sum(weight for key, weight in self._BOOSTS.items() if key in text)
        proba = min(round(proba, 3), 0.95)

        if proba >= 0.5:
            cls = self.CLASSES[2]
        elif proba >= 0.3:
            cls = self.CLASSES[1]
        else:
            cls = self.CLASSES[0]
        return {"proba": proba, "cls": cls}


_scorer: Scorer | None = None


def get_scorer() -> Scorer:
    """Единый экземпляр скорера на процесс (модель грузится один раз)."""
    global _scorer
    if _scorer is None:
        _scorer = Scorer()
    return _scorer
