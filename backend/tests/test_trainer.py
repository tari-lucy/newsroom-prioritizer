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


def test_scorer_handles_numeric_labels(monkeypatch, tmp_path):
    # Модель с ординальными метками 0/1/2 (не строками) должна встать без правок сервиса.
    texts, _ = _synthetic()
    numeric_labels = [2, 1, 0] * 10          # тот же порядок: высокая/средняя/низкая
    model_path = tmp_path / "model.joblib"
    save_model(train_model(texts, numeric_labels, min_df=1), str(model_path))

    import pipeline.scoring as scoring
    monkeypatch.setattr(scoring, "get_settings", lambda: type("S", (), {"MODEL_PATH": str(model_path)}))

    result = scoring.Scorer().score("атака бпла севастополь", "взрыв пожар")
    assert result["cls"] in ("низкая", "средняя", "высокая")
    assert 0.0 <= result["proba"] <= 1.0


def test_scorer_unwraps_dict_artifact(monkeypatch, tmp_path):
    # Модель, сохранённая словарём {'model': pipe, ...}, должна корректно распаковаться.
    import joblib
    pipe = train_model(*_synthetic(), min_df=1)
    model_path = tmp_path / "model.joblib"
    joblib.dump({"model": pipe, "meta": {"version": 1}}, str(model_path))

    import pipeline.scoring as scoring
    monkeypatch.setattr(scoring, "get_settings", lambda: type("S", (), {"MODEL_PATH": str(model_path)}))

    scorer = scoring.Scorer()
    assert scorer.model is not None
    result = scorer.score("атака бпла севастополь", "взрыв")
    assert result["cls"] in ("низкая", "средняя", "высокая")


def test_retrain_skips_without_labels(client):
    from trainer.retrain import run_retrain
    # Метки из Метрики ещё не подключены -> петля честно сообщает «недостаточно данных».
    assert run_retrain()["status"] == "skipped"


def test_retrain_survives_labeling_error(client, monkeypatch):
    import trainer.retrain as retrain

    def boom(session):
        raise RuntimeError("БД недоступна")

    monkeypatch.setattr(retrain, "build_training_frame", boom)
    result = retrain.run_retrain()
    assert result["status"] == "error"
    assert result["stage"] == "labeling"


def test_evaluate_single_class_does_not_crash():
    pipeline = train_model(*_synthetic(), min_df=1)
    # holdout из одного класса — PR-AUC не определён, но исключения быть не должно.
    metrics = evaluate(pipeline, ["атака бпла севастополь взрыв"] * 3, ["высокая"] * 3)
    assert metrics["pr_auc"] == 0.0
