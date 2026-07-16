def test_create_item_idempotent_on_url_conflict(client):
    """Параллельный сбор (ручной × автосбор) вставляет тот же url — не 500, а возврат существующего."""
    from sqlmodel import Session

    from database.database import engine
    from models.item import Item
    from services.crud.item import create_item

    with Session(engine) as s:
        first = create_item(Item(url="http://dup/1", title="A", body="a"), s)
        first_id = first.id
    with Session(engine) as s:
        second = create_item(Item(url="http://dup/1", title="B", body="b"), s)
        assert second.id == first_id   # тот же инфоповод, конфликт уникальности не уронил вставку


def test_ingest_summary(client, monkeypatch, fake_connector):
    monkeypatch.setattr("pipeline.ingest.get_connector", lambda source_type: fake_connector())
    client.post("/sources", json={"type": "rss", "name": "НТС", "params": {}})

    summary = client.post("/ingest").json()
    assert summary["fetched"] == 4
    assert summary["out_of_region"] == 1   # «Погода в Москве»
    assert summary["duplicates"] == 1      # почти-дубль u3
    assert summary["new"] == 2


def test_feed_filter_by_source(ingested):
    """Отбор по источнику считается в БД, а не по загруженной странице ленты."""
    source_id = ingested.get("/sources").json()[0]["id"]
    assert len(ingested.get("/feed", params={"source_id": source_id}).json()) == 2
    # Несуществующий источник — пустая лента, а не вся подряд.
    assert ingested.get("/feed", params={"source_id": 9999}).json() == []


def test_feed_filter_by_category(ingested):
    """Редактор отбирает первоисточники (правительство, МЧС) отдельно от пересказов в СМИ."""
    source_id = ingested.get("/sources").json()[0]["id"]
    # По умолчанию источник — СМИ, официальных инфоповодов нет.
    assert len(ingested.get("/feed", params={"category": "media"}).json()) == 2
    assert ingested.get("/feed", params={"category": "official"}).json() == []

    ingested.patch(f"/sources/{source_id}/category", params={"category": "official"})
    assert ingested.get("/feed", params={"category": "media"}).json() == []
    assert len(ingested.get("/feed", params={"category": "official"}).json()) == 2


def test_feed_search_by_text(ingested):
    found = ingested.get("/feed", params={"q": "дрон"}).json()
    assert [i["title"] for i in found] == ["Атака БПЛА на Севастополь"]
    assert ingested.get("/feed", params={"q": "такого-текста-нет"}).json() == []


def test_feed_filter_by_proba_range(ingested):
    feed = ingested.get("/feed").json()
    probas = sorted(i["score_proba"] for i in feed)
    # Верхняя граница строгая, нижняя — нет: диапазоны классов стыкуются без дыр и пересечений.
    low = ingested.get("/feed", params={"max_proba": probas[-1]}).json()
    assert all(i["score_proba"] < probas[-1] for i in low)
    high = ingested.get("/feed", params={"min_proba": probas[-1]}).json()
    assert all(i["score_proba"] >= probas[-1] for i in high)


def test_feed_filter_by_days(ingested):
    # Инфоповоды из фикстуры опубликованы в 2026 году — за последние сутки их нет.
    assert ingested.get("/feed", params={"days": 1}).json() == []
    assert len(ingested.get("/feed", params={"days": 36500}).json()) == 2


def test_feed_filters_and_sorting(ingested):
    feed = ingested.get("/feed").json()
    titles = [item["title"] for item in feed]

    # Чужой регион и дубль в ленту не попадают.
    assert "Погода в Москве" not in titles
    assert len(feed) == 2

    # Свежие сверху: даты публикации убывают.
    dates = [item["published_at"] for item in feed]
    assert dates == sorted(dates, reverse=True)

    # Самый свежий — про атаку на Севастополь (гео-термин на месте).
    top = feed[0]
    assert "севастопол" in top["matched_terms"]
