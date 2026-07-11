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
