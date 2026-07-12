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
