def test_feedback_upsert_and_export(ingested):
    item_id = ingested.get("/feed").json()[0]["id"]

    assert ingested.post(f"/feedback/{item_id}", json={"verdict": "like"}).status_code == 200
    # Смена мнения обновляет ту же запись, а не создаёт новую.
    ingested.post(f"/feedback/{item_id}", json={"verdict": "dislike"})

    export = ingested.get("/feedback").json()
    assert len(export) == 1
    assert export[0]["verdict"] == "dislike"
    assert export[0]["title"]           # контекст инфоповода присутствует

    # Оценка отражается в ленте.
    feed_item = [i for i in ingested.get("/feed").json() if i["id"] == item_id][0]
    assert feed_item["feedback"] == "dislike"


def test_invalid_verdict(ingested):
    item_id = ingested.get("/feed").json()[0]["id"]
    assert ingested.post(f"/feedback/{item_id}", json={"verdict": "meh"}).status_code == 400


def test_feedback_missing_item(ingested):
    assert ingested.post("/feedback/999", json={"verdict": "like"}).status_code == 404
