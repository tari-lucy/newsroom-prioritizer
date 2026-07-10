"""Оценка модели и гейт промоута.

Главная метрика — PR-AUC по высокому классу (дисбаланс ~1:4, ROC-AUC завышает). Кандидат
заменяет текущую модель только если не хуже её на holdout — защита от деградации на шумном месяце.
"""
from typing import Optional

import numpy as np
from sklearn.metrics import average_precision_score

POSITIVE_CLASS = "высокая"


def evaluate(pipeline, texts: list[str], labels: list[str]) -> dict:
    """PR-AUC по классу «высокая» на переданной выборке."""
    proba = pipeline.predict_proba(texts)
    classes = list(pipeline.classes_)
    pos_idx = classes.index(POSITIVE_CLASS) if POSITIVE_CLASS in classes else len(classes) - 1
    y_true = np.array([1 if label == POSITIVE_CLASS else 0 for label in labels])
    # PR-AUC не определён, если в выборке один класс — возвращаем 0.0, а не исключение.
    if len(np.unique(y_true)) < 2:
        return {"pr_auc": 0.0}
    pr_auc = average_precision_score(y_true, proba[:, pos_idx])
    return {"pr_auc": float(pr_auc)}


def passes_gate(candidate: dict, current: Optional[dict], margin: float = 0.0) -> bool:
    """Промоутить кандидата? Да, если текущей модели нет или кандидат не хуже её на margin."""
    if current is None:
        return True
    return candidate["pr_auc"] >= current["pr_auc"] - margin
