def test_register_and_login(client):
    assert client.post("/auth/register", json={"username": "editor1", "password": "secret123"}).status_code == 201
    resp = client.post("/auth/login", data={"username": "editor1", "password": "secret123"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "editor2", "password": "secret123"})
    assert client.post("/auth/login", data={"username": "editor2", "password": "wrong"}).status_code == 401


def test_register_duplicate_username(client):
    client.post("/auth/register", json={"username": "editor3", "password": "secret123"})
    # Повторная регистрация того же логина — 400, а не второй аккаунт.
    resp = client.post("/auth/register", json={"username": "editor3", "password": "other123"})
    assert resp.status_code == 400


def test_register_rejects_weak_credentials(client):
    # Короткий пароль и короткий логин не проходят валидацию схемы.
    assert client.post("/auth/register", json={"username": "editor4", "password": "123"}).status_code == 422
    assert client.post("/auth/register", json={"username": "ab", "password": "secret123"}).status_code == 422


def test_register_open_when_no_invite_code(client):
    # По умолчанию код не задан -> регистрация открыта, поле не требуется.
    assert client.get("/auth/invite-required").json()["required"] is False
    assert client.post("/auth/register", json={"username": "editor5", "password": "secret123"}).status_code == 201


def test_register_requires_invite_code(client, monkeypatch):
    from database.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("REGISTRATION_INVITE_CODE", "letmein")
    try:
        assert client.get("/auth/invite-required").json()["required"] is True
        # Без кода и с неверным кодом — 403; с верным — заводим редактора.
        assert client.post("/auth/register", json={"username": "editor6", "password": "secret123"}).status_code == 403
        assert client.post("/auth/register", json={
            "username": "editor6", "password": "secret123", "invite_code": "wrong"}).status_code == 403
        assert client.post("/auth/register", json={
            "username": "editor6", "password": "secret123", "invite_code": "letmein"}).status_code == 201
    finally:
        get_settings.cache_clear()   # не протекаем настройкой в соседние тесты


def test_protected_endpoint_requires_token(client):
    # Снимаем тестовый обход авторизации — без токена доступ к ленте закрыт.
    import main
    main.app.dependency_overrides.clear()
    assert client.get("/feed").status_code == 401
