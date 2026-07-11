"""Витрина редактора: лента инфоповодов по приоритету и управление источниками."""
import os
import time

import streamlit as st
# streamlit-cookies-manager использует устаревший st.cache — подменяем на актуальный.
st.cache = st.cache_data

import requests
from streamlit_cookies_manager import EncryptedCookieManager

API_URL = os.environ.get("API_URL", "http://api:8000")
COOKIE_PASSWORD = os.environ.get("COOKIE_PASSWORD", "newsroom-cookie-key")

# Индикатор потенциала: огонёк = «может зайти», ниже — прохладнее.
POTENTIAL_ICON = {"высокая": "🔥", "средняя": "🌤️", "низкая": "💤"}
SOURCE_TYPES = ["rss", "telegram", "vk"]

# Основы гео-терминов из region.yml → читаемые названия для карточки.
REGION_NAMES = {
    "севастопол": "Севастополь", "крым": "Крым", "симферопол": "Симферополь",
    "ялт": "Ялта", "керч": "Керчь", "балаклав": "Балаклава", "евпатор": "Евпатория",
    "феодос": "Феодосия", "бахчисара": "Бахчисарай", "джанко": "Джанкой",
    "алушт": "Алушта", "саки": "Саки", "черноморск": "Черноморское",
    "инкерман": "Инкерман", "гурзуф": "Гурзуф", "форос": "Форос",
    "херсонес": "Херсонес", "развожаев": "Развожаев", "аксёнов": "Аксёнов",
}


def region_label(terms):
    names = [REGION_NAMES.get(t, t.capitalize()) for t in (terms or [])]
    return ", ".join(dict.fromkeys(names))


# --- Обёртки над API: подстановка токена и единая обработка ошибок сети ---

def _headers():
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_get(path: str, **params):
    resp = requests.get(f"{API_URL}{path}", params=params, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def api_post(path: str, **kwargs):
    resp = requests.post(f"{API_URL}{path}", headers=_headers(), timeout=60, **kwargs)
    resp.raise_for_status()
    return resp.json() if resp.content else None


def api_patch(path: str, **params):
    resp = requests.patch(f"{API_URL}{path}", params=params, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def api_delete(path: str):
    resp = requests.delete(f"{API_URL}{path}", headers=_headers(), timeout=15)
    resp.raise_for_status()


def do_login(username: str, password: str):
    """Логин через /auth/login (форма OAuth2). Токен — в сессию и в cookie (переживает F5)."""
    resp = requests.post(
        f"{API_URL}/auth/login",
        data={"username": username, "password": password},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    st.session_state["token"] = token
    cookies["token"] = token
    cookies.save()


def render_login():
    """Экран входа. Показывается, пока редактор не авторизован."""
    st.subheader("Вход")
    st.info("👤 **Демо-доступ для проверки:** логин **`editor`**, пароль **`editor123`**")
    with st.form("login"):
        username = st.text_input("Логин", value="editor")
        password = st.text_input("Пароль", type="password")
        if st.form_submit_button("Войти"):
            try:
                do_login(username, password)
                st.rerun()
            except requests.RequestException:
                st.error("Неверный логин или пароль.")


# --- Страница «Лента» ---

def page_feed():
    st.subheader("Лента инфоповодов")
    st.caption("Свежие сверху, внутри дня — по потенциалу «залететь». Показаны только релевантные региону.")

    try:
        items = api_get("/feed", limit=100)
    except requests.RequestException as e:
        st.error(f"Не удалось получить ленту: {e}")
        return

    if not items:
        st.info("Лента пуста. Нажмите «Запустить сбор» в боковой панели, чтобы собрать инфоповоды.")
        return

    for item in items:
        with st.container(border=True):
            score_col, main_col = st.columns([1, 7])

            with score_col:
                cls = item.get("score_class") or ""
                proba = item.get("score_proba")
                chance = f"{proba:.0%}" if proba is not None else "—"
                st.markdown(
                    f"<div style='text-align:center'>"
                    f"<div style='font-size:2.4rem;line-height:1.1'>{POTENTIAL_ICON.get(cls, '')}</div>"
                    f"<div style='font-weight:600'>{cls}</div>"
                    f"<div style='color:gray;font-size:0.85rem'>шанс {chance}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            with main_col:
                st.markdown(f"##### [{item['title']}]({item['url']})")
                meta = " · ".join(p for p in [
                    item.get("source_name"),
                    (item.get("published_at") or "")[:10] or None,
                ] if p)
                region = region_label(item.get("matched_terms"))
                caption = meta + (f"  ·  📍 {region}" if region else "")
                if caption:
                    st.caption(caption)

                body = item.get("body") or ""
                if body:
                    st.write(body[:280] + ("…" if len(body) > 280 else ""))
                    if len(body) > 280:
                        with st.expander("📄 Полный текст"):
                            st.write(body)

                _rewrite_control(item["id"])
                _feedback_control(item)


def _feedback_control(item):
    """Оценка редактора (👍/👎). Копится как сигнал для дообучения модели."""
    verdict = item.get("feedback")
    st.caption("Оценка редактора — пригодится для дообучения модели:")
    cols = st.columns([2, 2, 6])
    like = ("✅ " if verdict == "like" else "") + "👍 Стоящий"
    dislike = ("✅ " if verdict == "dislike" else "") + "👎 Мимо"
    if cols[0].button(like, key=f"like_{item['id']}"):
        _send_feedback(item["id"], "like")
    if cols[1].button(dislike, key=f"dislike_{item['id']}"):
        _send_feedback(item["id"], "dislike")


def _send_feedback(item_id: int, verdict: str):
    try:
        api_post(f"/feedback/{item_id}", json={"verdict": verdict})
        st.rerun()
    except requests.RequestException as e:
        st.error(f"Не удалось сохранить оценку: {e}")


def _rewrite_control(item_id: int):
    """Кнопка рерайта: ставит задачу в очередь и опрашивает статус до готовности."""
    state_key = f"rewrite_{item_id}"

    if st.button("✍️ Рерайт", key=f"btn_rw_{item_id}"):
        try:
            api_post(f"/rewrite/{item_id}")
            with st.spinner("Готовим рерайт…"):
                result = None
                # Рерайт считает воркер асинхронно — опрашиваем статус до готовности.
                for _ in range(20):
                    time.sleep(0.5)
                    result = api_get(f"/rewrite/{item_id}")
                    if result and result["status"] in ("done", "error"):
                        break
            if result and result["status"] == "done":
                st.session_state[state_key] = result
            elif result and result["status"] == "error":
                st.error("Рерайт не удался.")
            else:
                st.warning("Рерайт ещё готовится — откройте позже.")
        except requests.RequestException as e:
            st.error(f"Не удалось запросить рерайт: {e}")

    stored = st.session_state.get(state_key)
    if stored:
        with st.expander("✍️ Рерайт", expanded=True):
            st.write(stored.get("text", ""))
            if stored.get("uniqueness") is not None:
                st.caption(f"Уникальность: {stored['uniqueness']}%")


# --- Страница «Источники» ---

def page_sources():
    st.subheader("Источники")
    st.caption("Ленты, которые опрашивает сервис. Источники можно добавлять и выключать.")

    with st.form("add_source", clear_on_submit=True):
        st.markdown("**Добавить источник**")
        col_type, col_name = st.columns([1, 2])
        src_type = col_type.selectbox("Тип", SOURCE_TYPES, index=0)
        src_name = col_name.text_input("Название")
        src_url = st.text_input("URL ленты (для rss)")
        submitted = st.form_submit_button("Добавить")
        if submitted:
            if not src_name or not src_url:
                st.warning("Заполните название и URL.")
            else:
                try:
                    api_post("/sources", json={
                        "type": src_type,
                        "name": src_name,
                        "params": {"url": src_url},
                    })
                    st.success(f"Источник «{src_name}» добавлен.")
                    st.rerun()
                except requests.RequestException as e:
                    st.error(f"Не удалось добавить источник: {e}")

    try:
        sources = api_get("/sources")
    except requests.RequestException as e:
        st.error(f"Не удалось получить источники: {e}")
        return

    st.markdown("**Список источников**")
    for src in sources:
        cols = st.columns([3, 1, 2, 1, 1])
        cols[0].write(f"**{src['name']}**")
        cols[1].write(src["type"])
        cols[2].caption(src.get("params", {}).get("url", ""))
        # Переключатель активности.
        if src["active"]:
            if cols[3].button("Выкл", key=f"off_{src['id']}"):
                api_patch(f"/sources/{src['id']}/active", active=False)
                st.rerun()
        else:
            if cols[3].button("Вкл", key=f"on_{src['id']}"):
                api_patch(f"/sources/{src['id']}/active", active=True)
                st.rerun()
        if cols[4].button("Удалить", key=f"del_{src['id']}"):
            api_delete(f"/sources/{src['id']}")
            st.rerun()


# --- Компоновка ---

st.set_page_config(page_title="Newsroom Prioritizer", page_icon="📰", layout="wide")

# Cookie-менеджер: ДОЖИДАЕМСЯ загрузки cookie из браузера (ready), иначе вход не переживёт F5.
cookies = EncryptedCookieManager(prefix="newsroom/", password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()

st.title("📰 Newsroom Prioritizer")

# Восстанавливаем вход из cookie (переживает перезагрузку страницы F5).
if "token" not in st.session_state:
    st.session_state["token"] = cookies.get("token") or None

# Пока редактор не авторизован — показываем только экран входа.
if not st.session_state.get("token"):
    render_login()
    st.stop()

with st.sidebar:
    st.header("Навигация")
    page = st.radio("Раздел", ["Лента", "Источники"], label_visibility="collapsed")
    st.divider()
    if st.button("🚪 Выйти", use_container_width=True):
        st.session_state.pop("token", None)
        cookies["token"] = ""
        cookies.save()
        st.rerun()
    if st.button("🔄 Запустить сбор", use_container_width=True):
        with st.spinner("Идёт сбор инфоповодов…"):
            try:
                summary = api_post("/ingest")
                st.success(
                    f"Собрано: {summary['fetched']} · новых: {summary['new']} · "
                    f"дублей: {summary['duplicates']} · вне региона: {summary['out_of_region']}"
                )
            except requests.RequestException as e:
                st.error(f"Сбор не удался: {e}")

if page == "Лента":
    page_feed()
else:
    page_sources()
