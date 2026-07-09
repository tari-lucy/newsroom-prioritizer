def test_register_and_login(client):
    assert client.post("/auth/register", json={"username": "u1", "password": "p1"}).status_code == 201
    resp = client.post("/auth/login", data={"username": "u1", "password": "p1"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "u2", "password": "p2"})
    assert client.post("/auth/login", data={"username": "u2", "password": "wrong"}).status_code == 401


def test_protected_endpoint_requires_token(client):
    # Снимаем тестовый обход авторизации — без токена доступ к ленте закрыт.
    import main
    main.app.dependency_overrides.clear()
    assert client.get("/feed").status_code == 401
