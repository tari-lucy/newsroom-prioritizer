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

    # Сортировка по убыванию вероятности.
    probas = [item["score_proba"] for item in feed]
    assert probas == sorted(probas, reverse=True)

    # Инфоповод про атаку получает высокий приоритет и гео-термин.
    top = feed[0]
    assert top["score_class"] == "высокая"
    assert "севастопол" in top["matched_terms"]
