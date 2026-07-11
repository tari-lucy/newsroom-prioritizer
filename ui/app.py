"""Витрина редактора: лента инфоповодов по приоритету и управление источниками."""
import os
import time
from collections import Counter
from datetime import date, datetime, timedelta

import streamlit as st
# streamlit-cookies-manager использует устаревший st.cache — подменяем на актуальный.
st.cache = st.cache_data

import requests
from streamlit_cookies_manager import EncryptedCookieManager

API_URL = os.environ.get("API_URL", "http://api:8000")
COOKIE_PASSWORD = os.environ.get("COOKIE_PASSWORD", "newsroom-cookie-key")

# Индикатор потенциала: огонёк = «может зайти», ниже — прохладнее.
POTENTIAL_ICON = {"высокая": "🔥", "средняя": "🌤️", "низкая": "💤"}
# Тёплый→холодный акцент по классу (интуитивно: горячее = выше шанс).
POTENTIAL_COLOR = {"высокая": "#e8590c", "средняя": "#f59f00", "низкая": "#868e96"}
SOURCE_TYPES = ["rss", "telegram", "vk"]


CUSTOM_CSS = """
<style>
.block-container { padding-top: 2.5rem; max-width: 1080px; }
#MainMenu, footer { visibility: hidden; }
h5 a { text-decoration: none; }
[data-testid="stMetricValue"] { font-size: 1.5rem; }
div[data-testid="stExpander"] details { border: none; }
</style>
"""

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
    st.caption("Свежие сверху, внутри дня — по потенциалу «залететь». Только релевантные региону.")

    try:
        items = api_get("/feed", limit=300)
    except requests.RequestException as e:
        st.error(f"Не удалось получить ленту: {e}")
        return

    if not items:
        st.info("Лента пуста. Нажмите «Запустить сбор» в боковой панели, чтобы собрать инфоповоды.")
        return

    filtered = _feed_filters(items)
    _feed_counters(filtered)
    st.divider()

    if not filtered:
        st.info("Под выбранные фильтры ничего не подошло.")
        return
    for item in filtered:
        _render_card(item)


def _within_period(published_at, period):
    if period == "всё время":
        return True
    if not published_at:
        return False
    try:
        published = datetime.fromisoformat(published_at).date()
    except ValueError:
        return False
    threshold = {"сегодня": 0, "3 дня": 2, "неделя": 6}[period]
    return published >= date.today() - timedelta(days=threshold)


def _feed_filters(items):
    """Панель фильтров сверху; возвращает отфильтрованный список инфоповодов."""
    c = st.columns([3, 2, 2, 2])
    query = c[0].text_input("Поиск", placeholder="заголовок или текст")
    classes = c[1].multiselect("Класс", ["высокая", "средняя", "низкая"], placeholder="любой")
    sources = sorted({i.get("source_name") for i in items if i.get("source_name")})
    source = c[2].selectbox("Источник", ["Все источники", *sources])
    period = c[3].selectbox("Период", ["всё время", "сегодня", "3 дня", "неделя"])

    q = query.strip().lower()
    result = []
    for item in items:
        if q and q not in f"{item.get('title', '')} {item.get('body') or ''}".lower():
            continue
        if classes and item.get("score_class") not in classes:
            continue
        if source != "Все источники" and item.get("source_name") != source:
            continue
        if not _within_period(item.get("published_at"), period):
            continue
        result.append(item)
    return result


def _feed_counters(items):
    counts = Counter(i.get("score_class") for i in items)
    cols = st.columns(4)
    cols[0].metric("Всего", len(items))
    cols[1].metric("🔥 Высокие", counts.get("высокая", 0))
    cols[2].metric("🌤️ Средние", counts.get("средняя", 0))
    cols[3].metric("💤 Низкие", counts.get("низкая", 0))


def _render_card(item):
    cls = item.get("score_class") or ""
    color = POTENTIAL_COLOR.get(cls, "#868e96")
    with st.container(border=True):
        score_col, main_col = st.columns([1, 7])

        with score_col:
            proba = item.get("score_proba")
            chance = f"{proba:.0%}" if proba is not None else "—"
            st.markdown(
                f"<div style='text-align:center'>"
                f"<div style='font-size:2.4rem;line-height:1.1'>{POTENTIAL_ICON.get(cls, '')}</div>"
                f"<div style='display:inline-block;padding:1px 10px;border-radius:12px;"
                f"background:{color}22;color:{color};font-weight:600;font-size:0.9rem'>{cls}</div>"
                f"<div style='color:gray;font-size:0.85rem;margin-top:3px'>шанс {chance}</div>"
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

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
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
