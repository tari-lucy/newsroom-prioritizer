from worker.rewrite_runner import generate_rewrite


def test_rewrite_enqueue(ingested, monkeypatch):
    # Брокер в тестах не поднят — подменяем публикацию, проверяем создание задачи pending.
    monkeypatch.setattr("routes.rewrite.publish_rewrite_task", lambda rewrite_id, item_id: None)
    item_id = ingested.get("/feed").json()[0]["id"]

    resp = ingested.post(f"/rewrite/{item_id}")
    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"

    status = ingested.get(f"/rewrite/{item_id}").json()
    assert status["status"] == "pending"


def test_rewrite_missing_item(client, monkeypatch):
    monkeypatch.setattr("routes.rewrite.publish_rewrite_task", lambda rewrite_id, item_id: None)
    assert client.post("/rewrite/999").status_code == 404


def test_generate_rewrite_stub():
    text, uniqueness = generate_rewrite("Пожар в Ялте", "В Ялте загорелся склад")
    assert "Пожар в Ялте" in text
    assert uniqueness is None
