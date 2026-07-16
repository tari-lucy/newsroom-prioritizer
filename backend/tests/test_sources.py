def test_source_crud(client):
    # Стартуем с пустого списка (сид отключён в тестах).
    assert client.get("/sources").json() == []

    resp = client.post("/sources", json={
        "type": "rss", "name": "НТС", "params": {"url": "http://example/rss"},
    })
    assert resp.status_code == 201
    source_id = resp.json()["id"]

    assert len(client.get("/sources").json()) == 1

    # Выключение не удаляет источник.
    toggled = client.patch(f"/sources/{source_id}/active", params={"active": False})
    assert toggled.json()["active"] is False

    # active_only фильтрует выключенные.
    assert client.get("/sources", params={"active_only": True}).json() == []

    assert client.delete(f"/sources/{source_id}").status_code == 204
    assert client.get("/sources").json() == []


def test_delete_missing_source(client):
    assert client.delete("/sources/999").status_code == 404


def test_source_category_defaults_and_changes(client):
    # Категория по умолчанию — СМИ: большинство лент такие, официальные редактор уточнит.
    created = client.post("/sources", json={"type": "rss", "name": "МЧС", "params": {}}).json()
    assert created["category"] == "media"

    changed = client.patch(f"/sources/{created['id']}/category", params={"category": "official"})
    assert changed.json()["category"] == "official"

    # Категория задаётся и при добавлении.
    vk = client.post("/sources", json={
        "type": "vk", "category": "official", "name": "Правительство", "params": {},
    }).json()
    assert vk["category"] == "official"


def test_source_category_validated(client):
    created = client.post("/sources", json={"type": "rss", "name": "Лента", "params": {}}).json()
    # Произвольная категория не принимается — набор значений закрыт.
    assert client.patch(f"/sources/{created['id']}/category", params={"category": "выдумка"}).status_code == 422
    assert client.patch("/sources/999/category", params={"category": "media"}).status_code == 404
