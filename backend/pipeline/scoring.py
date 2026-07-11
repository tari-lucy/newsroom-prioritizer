"""Приоритизатор «залетит / не залетит» — единая точка подключения модели.

Сейчас работает эвристика-заглушка, чтобы пайплайн был живым без обученной модели.
На шаге 7 в этом же классе заглушка заменяется на загрузку обученного приоритизатора
(virality_model.joblib) — остальной сервис (API, витрина) при этом не меняется.
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
        # Обученная модель (пайплайн текст → класс). Нет файла/неподходящий формат — работает заглушка.
        if os.path.exists(model_path):
            try:
                import joblib
                self.model = self._extract_estimator(joblib.load(model_path))
                if self.model is None:
                    logger.warning("Артефакт %s не содержит модели с predict_proba — работает заглушка", model_path)
                else:
                    logger.info("Загружена модель приоритизатора: %s", model_path)
            except Exception as e:
                logger.warning("Не удалось загрузить модель (%s): работает заглушка", e)

    @staticmethod
    def _extract_estimator(loaded):
        """Достаёт обученную модель из артефакта: поддерживает и «голый» estimator,
        и обёртку словарём ({'model': pipe} и т.п.)."""
        if hasattr(loaded, "predict_proba"):
            return loaded
        if isinstance(loaded, dict):
            for key in ("model", "pipeline", "estimator", "clf", "classifier"):
                candidate = loaded.get(key)
                if candidate is not None and hasattr(candidate, "predict_proba"):
                    return candidate
            for candidate in loaded.values():
                if hasattr(candidate, "predict_proba"):
                    return candidate
        return None

    def score(self, title: str, body: str) -> dict:
        """Возвращает {'proba': float, 'cls': str} — вероятность «залетит» и класс приоритета."""
        text = f"{title} {body}".strip()

        if self.model is not None:
            try:
                proba_vec = self.model.predict_proba([text])[0]
                classes = list(self.model.classes_)
                pred_idx = int(proba_vec.argmax())
                if self.CLASSES[2] in classes:
                    # Строковые метки низкая/средняя/высокая.
                    high_idx = classes.index(self.CLASSES[2])
                    cls = str(classes[pred_idx])
                else:
                    # Ординальные метки (напр. 0/1/2): высокий класс = максимальная метка.
                    ranked = sorted(range(len(classes)), key=lambda i: classes[i])
                    high_idx = ranked[-1]
                    cls = self.CLASSES[min(ranked.index(pred_idx), len(self.CLASSES) - 1)]
                # P(залетит) = вероятность высокого класса.
                return {"proba": round(float(proba_vec[high_idx]), 3), "cls": cls}
            except Exception as e:
                # Любая несовместимость модели не должна ронять сбор — откатываемся на заглушку.
                logger.warning("Ошибка предсказания моделью (%s) — использую заглушку", e)

        # Заглушка-эвристика, пока обученной модели нет.
        text_lower = text.lower()
        proba = 0.15 + sum(weight for key, weight in self._BOOSTS.items() if key in text_lower)
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
