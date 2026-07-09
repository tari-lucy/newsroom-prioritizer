"""Тесты петли переобучения: обучение, оценка, гейт, загрузка модели скорером."""
from trainer.evaluate import evaluate, passes_gate
from trainer.train import save_model, train_model


def _synthetic():
    """Разделимые синтетические данные по трём классам приоритета."""
    texts, labels = [], []
    for _ in range(10):
        texts.append("атака бпла севастополь взрыв пожар")
        labels.append("высокая")
        texts.append("совещание чиновников отчёт план бюджет")
        labels.append("средняя")
        texts.append("ремонт дороги благоустройство двор")
        labels.append("низкая")
    return texts, labels


def test_train_and_evaluate():
    texts, labels = _synthetic()
    pipeline = train_model(texts, labels, min_df=1)
    metrics = evaluate(pipeline, texts, labels)
    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert metrics["pr_auc"] > 0.8   # на разделимых данных сигнал сильный


def test_gate_logic():
    assert passes_gate({"pr_auc": 0.5}, None)               # нет текущей -> промоут
    assert passes_gate({"pr_auc": 0.5}, {"pr_auc": 0.45})   # лучше -> промоут
    assert not passes_gate({"pr_auc": 0.4}, {"pr_auc": 0.5})  # хуже -> оставляем текущую


def test_scorer_loads_trained_model(monkeypatch, tmp_path):
    texts, labels = _synthetic()
    model_path = tmp_path / "model.joblib"
    save_model(train_model(texts, labels, min_df=1), str(model_path))

    import pipeline.scoring as scoring
    monkeypatch.setattr(scoring, "get_settings", lambda: type("S", (), {"MODEL_PATH": str(model_path)}))

    scorer = scoring.Scorer()
    assert scorer.model is not None
    result = scorer.score("атака бпла севастополь", "взрыв пожар")
    assert result["cls"] in ("низкая", "средняя", "высокая")
    assert 0.0 <= result["proba"] <= 1.0


def test_retrain_skips_without_labels(client):
    from trainer.retrain import run_retrain
    # Метки из Метрики ещё не подключены -> петля честно сообщает «недостаточно данных».
    assert run_retrain()["status"] == "skipped"
