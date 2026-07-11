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


def test_factcheck_on_text(ingested):
    item_id = ingested.get("/feed").json()[0]["id"]
    # Фактчек по переданному тексту: без ключа LLM возвращает None, но не падает.
    resp = ingested.post(f"/rewrite/{item_id}/factcheck", json={"text": "Переписанный текст статьи."})
    assert resp.status_code == 200
    assert resp.json()["factcheck"] is None


def test_factcheck_empty_text(ingested):
    item_id = ingested.get("/feed").json()[0]["id"]
    assert ingested.post(f"/rewrite/{item_id}/factcheck", json={"text": "   "}).status_code == 400


def test_factcheck_missing_item(client):
    assert client.post("/rewrite/999/factcheck", json={"text": "текст"}).status_code == 404


def test_refine_without_key_returns_text(ingested):
    item_id = ingested.get("/feed").json()[0]["id"]
    # Без ключа LLM доработка возвращает текст как есть (не падает).
    resp = ingested.post(f"/rewrite/{item_id}/refine", json={"text": "Текущий текст", "instruction": "сократи"})
    assert resp.status_code == 200
    assert resp.json()["text"] == "Текущий текст"


def test_uniqueness_submit_without_key(ingested):
    item_id = ingested.get("/feed").json()[0]["id"]
    # Без ключа Text.ru отправка возвращает uid=None (сервис не падает).
    resp = ingested.post(f"/rewrite/{item_id}/uniqueness", json={"text": "x" * 200})
    assert resp.status_code == 200
    assert resp.json()["uid"] is None


def test_uniqueness_poll_without_key(ingested):
    item_id = ingested.get("/feed").json()[0]["id"]
    resp = ingested.get(f"/rewrite/{item_id}/uniqueness/SOME-UID")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True and body["uniqueness"] is None


def test_check_facts_no_key():
    from worker.factcheck import check_facts
    # Без ключа LLM фактчек недоступен -> None (сервис не падает).
    assert check_facts("Заголовок", "Исходный текст", "Переписанный текст") is None
