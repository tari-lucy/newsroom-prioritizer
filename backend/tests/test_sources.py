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
