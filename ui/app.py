"""Витрина редактора: лента инфоповодов по приоритету и управление источниками."""
import os
import time

import extra_streamlit_components as stx
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://api:8000")


@st.cache_resource
def get_cookie_manager():
    """Менеджер cookie — чтобы вход переживал перезагрузку страницы (F5)."""
    return stx.CookieManager(key="cookies")

# Цветовая индикация класса приоритета.
CLASS_BADGE = {
    "высокая": "🔴 высокая",
    "средняя": "🟡 средняя",
    "низкая": "⚪ низкая",
}
SOURCE_TYPES = ["rss", "telegram", "vk"]


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
    get_cookie_manager().set("token", token)


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
                time.sleep(0.3)   # дать cookie записаться до перезагрузки
                st.rerun()
            except requests.RequestException:
                st.error("Неверный логин или пароль.")


# --- Страница «Лента» ---

def page_feed():
    st.subheader("Лента инфоповодов")
    st.caption("Отсортировано по вероятности «залетит». Показаны только релевантные региону.")

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
            left, right = st.columns([1, 6])
            with left:
                proba = item.get("score_proba")
                st.metric("P(залетит)", f"{proba:.0%}" if proba is not None else "—")
                st.write(CLASS_BADGE.get(item.get("score_class"), item.get("score_class") or ""))
            with right:
                st.markdown(f"**[{item['title']}]({item['url']})**")
                meta = " · ".join(
                    part for part in [
                        item.get("source_name"),
                        (item.get("published_at") or "")[:10] or None,
                    ] if part
                )
                if meta:
                    st.caption(meta)
                terms = item.get("matched_terms") or []
                if terms:
                    st.caption("🗺 регион: " + ", ".join(terms))
                body = item.get("body") or ""
                if body:
                    preview = body[:300] + ("…" if len(body) > 300 else "")
                    st.write(preview)

                _feedback_control(item)
                _rewrite_control(item["id"])


def _feedback_control(item):
    """Кнопки 👍/👎. Текущая оценка приходит вместе с лентой и подсвечивается галочкой."""
    verdict = item.get("feedback")
    cols = st.columns([1, 1, 8])
    if cols[0].button("👍" + (" ✓" if verdict == "like" else ""), key=f"like_{item['id']}"):
        _send_feedback(item["id"], "like")
    if cols[1].button("👎" + (" ✓" if verdict == "dislike" else ""), key=f"dislike_{item['id']}"):
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
st.title("📰 Newsroom Prioritizer")

cookie_manager = get_cookie_manager()
# Восстанавливаем вход из cookie, чтобы сессия переживала перезагрузку страницы (F5).
if "token" not in st.session_state:
    saved_token = cookie_manager.get("token")
    if saved_token:
        st.session_state["token"] = saved_token

# Пока редактор не авторизован — показываем только экран входа.
if "token" not in st.session_state:
    render_login()
    st.stop()

with st.sidebar:
    st.header("Навигация")
    page = st.radio("Раздел", ["Лента", "Источники"], label_visibility="collapsed")
    st.divider()
    if st.button("🚪 Выйти", use_container_width=True):
        st.session_state.pop("token", None)
        cookie_manager.delete("token")
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
