"""Оркестрация переобучения: дозревшие метки → обучение → out-of-time гейт → промоут.

Кандидат обучается на всей истории, кроме последнего месяца; последний месяц — holdout для
честного сравнения с текущей моделью. Новая модель заменяет текущую только если проходит гейт.
Промоут = сохранение артефакта в MODEL_PATH, откуда его подхватывает Scorer.
"""
import logging
import os

from sqlmodel import Session

from database.config import get_settings
from database.database import engine
from trainer.evaluate import evaluate, passes_gate
from trainer.labeler import build_training_frame
from trainer.train import load_model, save_model, train_model
# Импорт моделей нужен для конфигурации маппера вне процесса API.
import models  # noqa: F401

logger = logging.getLogger(__name__)


def run_retrain() -> dict:
    settings = get_settings()

    with Session(engine) as session:
        texts, labels, months = build_training_frame(session)

    # Данных или классов мало — не переобучаемся (частая и нормальная ситуация на старте).
    if len(texts) < settings.RETRAIN_MIN_SAMPLES or len(set(labels)) < 2:
        logger.info("Недостаточно размеченных данных для переобучения (примеров: %d)", len(texts))
        return {"status": "skipped", "reason": "not_enough_data", "samples": len(texts)}

    # Out-of-time сплит: последний месяц — holdout.
    holdout_month = max(months)
    train_idx = [i for i, m in enumerate(months) if m != holdout_month]
    test_idx = [i for i, m in enumerate(months) if m == holdout_month]

    candidate = train_model([texts[i] for i in train_idx], [labels[i] for i in train_idx])
    candidate_metrics = evaluate(candidate, [texts[i] for i in test_idx], [labels[i] for i in test_idx])

    current_metrics = None
    if os.path.exists(settings.MODEL_PATH):
        current = load_model(settings.MODEL_PATH)
        current_metrics = evaluate(current, [texts[i] for i in test_idx], [labels[i] for i in test_idx])

    if passes_gate(candidate_metrics, current_metrics, settings.RETRAIN_GATE_MARGIN):
        save_model(candidate, settings.MODEL_PATH)
        logger.info("Модель обновлена: PR-AUC %.3f (была %s)",
                    candidate_metrics["pr_auc"], current_metrics)
        return {"status": "promoted", "candidate": candidate_metrics, "previous": current_metrics}

    logger.info("Кандидат не прошёл гейт (%.3f) — оставляем текущую модель", candidate_metrics["pr_auc"])
    return {"status": "kept_current", "candidate": candidate_metrics, "current": current_metrics}
