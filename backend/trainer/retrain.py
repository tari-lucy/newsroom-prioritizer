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
    """Прогон переобучения. Никогда не бросает исключение — возвращает статус-словарь.

    Возможные status: skipped (мало данных/один месяц/один класс), error (сбой этапа),
    promoted (модель обновлена), kept_current (кандидат не прошёл гейт).
    """
    settings = get_settings()

    # Этап 1: сбор размеченных данных (Метрика/БД). Сбой здесь не должен ронять петлю.
    try:
        with Session(engine) as session:
            texts, labels, months = build_training_frame(session)
    except Exception as e:
        logger.error("Сбор обучающих данных не удался: %s", e)
        return {"status": "error", "stage": "labeling", "error": str(e)}

    # Данных или классов мало — не переобучаемся (частая и нормальная ситуация на старте).
    if len(texts) < settings.RETRAIN_MIN_SAMPLES or len(set(labels)) < 2:
        logger.info("Недостаточно размеченных данных для переобучения (примеров: %d)", len(texts))
        return {"status": "skipped", "reason": "not_enough_data", "samples": len(texts)}

    # Out-of-time сплит: последний месяц — holdout.
    holdout_month = max(months)
    train_idx = [i for i, m in enumerate(months) if m != holdout_month]
    test_idx = [i for i, m in enumerate(months) if m == holdout_month]
    if not train_idx or not test_idx:
        logger.info("Все данные в одном месяце — out-of-time сплит невозможен")
        return {"status": "skipped", "reason": "single_month", "samples": len(texts)}

    test_texts = [texts[i] for i in test_idx]
    test_labels = [labels[i] for i in test_idx]
    if len(set(test_labels)) < 2:
        logger.info("В holdout один класс — честная оценка невозможна")
        return {"status": "skipped", "reason": "holdout_single_class"}

    # Этап 2: обучение и оценка кандидата.
    try:
        candidate = train_model([texts[i] for i in train_idx], [labels[i] for i in train_idx])
        candidate_metrics = evaluate(candidate, test_texts, test_labels)
    except Exception as e:
        logger.error("Обучение/оценка кандидата не удались: %s", e)
        return {"status": "error", "stage": "training", "error": str(e)}

    # Этап 3: оценка текущей модели (если она есть и читается).
    current_metrics = None
    if os.path.exists(settings.MODEL_PATH):
        try:
            current_metrics = evaluate(load_model(settings.MODEL_PATH), test_texts, test_labels)
        except Exception as e:
            logger.warning("Текущая модель не читается/не оценивается: %s — считаем, что её нет", e)

    # Этап 4: гейт и промоут.
    if passes_gate(candidate_metrics, current_metrics, settings.RETRAIN_GATE_MARGIN):
        try:
            save_model(candidate, settings.MODEL_PATH)
        except Exception as e:
            logger.error("Не удалось сохранить модель: %s", e)
            return {"status": "error", "stage": "save", "error": str(e)}
        logger.info("Модель обновлена: PR-AUC %.3f (была %s)", candidate_metrics["pr_auc"], current_metrics)
        return {"status": "promoted", "candidate": candidate_metrics, "previous": current_metrics}

    logger.info("Кандидат не прошёл гейт (%.3f) — оставляем текущую", candidate_metrics["pr_auc"])
    return {"status": "kept_current", "candidate": candidate_metrics, "current": current_metrics}
