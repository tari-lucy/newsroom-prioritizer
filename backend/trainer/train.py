"""Обучение приоритизатора. Конфигурация — победившая в модуле моделирования:
TF-IDF по словам + символьным n-граммам (char_wb) → мультиклассовая LogReg.
Символьные n-граммы устойчивы к словоформам и новой лексике будущих месяцев.
"""
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline


def build_pipeline(min_df: int = 5, max_features: int = 30000, c: float = 0.59) -> Pipeline:
    """Собирает пайплайн «сырой текст → класс приоритета». Параметры по умолчанию — конфиг Optuna."""
    features = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 1),
                                 min_df=min_df, max_features=max_features)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                 min_df=min_df, max_features=max_features)),
    ])
    clf = LogisticRegression(C=c, class_weight="balanced", max_iter=1000)
    return Pipeline([("tfidf", features), ("clf", clf)])


def train_model(texts: list[str], labels: list[str], **kwargs) -> Pipeline:
    pipeline = build_pipeline(**kwargs)
    pipeline.fit(texts, labels)
    return pipeline


def save_model(pipeline: Pipeline, path: str) -> None:
    joblib.dump(pipeline, path)


def load_model(path: str) -> Pipeline:
    return joblib.load(path)
