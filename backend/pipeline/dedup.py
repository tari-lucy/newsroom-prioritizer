"""Дедуп инфоповодов. По выводам EDA настоящие текст-дубли отделяются только на
высоком пороге косинуса (~0.9); символьные n-граммы при низком пороге ловят шаблонные
рубрики (ложные дубли), поэтому порог держим высоким.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def best_match(new_text: str, candidate_texts: list[str]) -> tuple[int, float]:
    """Ищет ближайший по тексту инфоповод среди кандидатов.

    Возвращает (индекс кандидата, косинусное сходство). Если кандидатов нет — (-1, 0.0).
    Символьные n-граммы (char_wb 3–5) устойчивы к словоформам — тот же приём, что победил
    в моделировании.
    """
    if not candidate_texts:
        return -1, 0.0

    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
    matrix = vectorizer.fit_transform([new_text] + candidate_texts)
    similarities = cosine_similarity(matrix[0], matrix[1:]).ravel()
    best_idx = int(similarities.argmax())
    return best_idx, float(similarities[best_idx])
