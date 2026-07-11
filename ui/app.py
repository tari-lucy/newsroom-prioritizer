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
# Порог класса по шансу «залететь» (вероятность высокого класса). Правится тут.
POTENTIAL_THRESHOLDS = [(0.60, "высокая"), (0.30, "средняя")]
SOURCE_TYPES = ["rss", "telegram", "vk"]


def potential(proba):
    """Класс инфоповода по шансу залететь: понятный порог, а не решение модели argmax."""
    if proba is not None:
        for threshold, name in POTENTIAL_THRESHOLDS:
            if proba >= threshold:
                return name
    return "низкая"


def format_paragraphs(text):
    """Разбивает текст на читаемые абзацы (одиночные переносы строк → отдельные абзацы)."""
    parts = [p.strip() for p in (text or "").replace("\r", "").split("\n") if p.strip()]
    return "\n\n".join(parts)


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
        items = api_get("/feed", limit=100)
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

    # Пагинация: рисуем ограниченное число карточек за раз — иначе Streamlit подвисает.
    page_size = 20
    total = len(filtered)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(st.session_state.get("feed_page", 1), pages)

    start = (page - 1) * page_size
    st.caption(f"Показаны {start + 1}–{min(start + page_size, total)} из {total}  ·  страница {page} из {pages}")
    for item in filtered[start:start + page_size]:
        _render_card(item)

    # Навигация по страницам — внизу под лентой.
    if pages > 1:
        st.divider()
        nav = st.columns([1, 2, 1])
        if nav[0].button("← Назад", disabled=page <= 1, use_container_width=True):
            st.session_state["feed_page"] = page - 1
            st.rerun()
        nav[1].markdown(
            f"<div style='text-align:center;padding-top:6px'>страница {page} из {pages}</div>",
            unsafe_allow_html=True,
        )
        if nav[2].button("Вперёд →", disabled=page >= pages, use_container_width=True):
            st.session_state["feed_page"] = page + 1
            st.rerun()


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
        if classes and potential(item.get("score_proba")) not in classes:
            continue
        if source != "Все источники" and item.get("source_name") != source:
            continue
        if not _within_period(item.get("published_at"), period):
            continue
        result.append(item)
    return result


def _feed_counters(items):
    counts = Counter(potential(i.get("score_proba")) for i in items)
    cols = st.columns(4)
    cols[0].metric("Всего", len(items))
    cols[1].metric("🔥 Высокие", counts.get("высокая", 0))
    cols[2].metric("🌤️ Средние", counts.get("средняя", 0))
    cols[3].metric("💤 Низкие", counts.get("низкая", 0))


def _render_card(item):
    cls = potential(item.get("score_proba"))
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

            _feedback_control(item)
            if st.button("📄 Открыть карточку", key=f"open_{item['id']}", use_container_width=True):
                st.session_state["open_item"] = item
                st.rerun()


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


# --- Детальная карточка инфоповода ---

def page_item_detail(item):
    if st.button("← Назад к ленте"):
        st.session_state.pop("open_item", None)
        st.rerun()

    cls = potential(item.get("score_proba"))
    proba = item.get("score_proba")
    chance = f"{proba:.0%}" if proba is not None else "—"

    st.markdown(f"### {item['title']}")
    meta = " · ".join(p for p in [
        item.get("source_name"),
        (item.get("published_at") or "")[:10] or None,
    ] if p)
    region = region_label(item.get("matched_terms"))
    st.caption(meta + (f"  ·  📍 {region}" if region else ""))
    st.markdown(
        f"{POTENTIAL_ICON.get(cls, '')} **{cls}** · шанс {chance}  ·  [первоисточник]({item['url']})"
    )
    st.divider()

    st.subheader("Текст инфоповода")
    st.write(format_paragraphs(item.get("body")) or "—")
    st.divider()

    st.subheader("Рерайт под стиль редакции")
    _detail_rewrite(item)
    st.divider()

    _feedback_control(item)


def _detail_rewrite(item):
    """Верстак рерайта: генерация → ручная правка → доработка ИИ → проверки → копирование."""
    item_id = item["id"]
    work_key = f"work_{item_id}"
    st.session_state.setdefault(work_key, "")

    def apply_refine(instruction):
        current = st.session_state.get(work_key, "")
        if not current.strip():
            st.warning("Сначала должен быть текст (сгенерируйте или впишите).")
            return
        with st.spinner("Дорабатываю…"):
            try:
                res = api_post(f"/rewrite/{item_id}/refine", json={"text": current, "instruction": instruction})
                st.session_state[work_key] = (res or {}).get("text", current)
                st.rerun()
            except requests.RequestException as e:
                st.error(f"Не удалось доработать: {e}")

    # 1. Одна кнопка: ставит задачу в очередь, ждёт и сама загружает результат в поле.
    gen = st.columns([2, 2, 4])
    if gen[0].button("✍️ Сгенерировать рерайт"):
        try:
            api_post(f"/rewrite/{item_id}")
            loaded = False
            with st.spinner("Готовим рерайт…"):
                for _ in range(12):
                    time.sleep(1)
                    rewrite = api_get(f"/rewrite/{item_id}")
                    if rewrite and rewrite.get("status") == "done" and rewrite.get("text"):
                        st.session_state[work_key] = rewrite["text"]
                        loaded = True
                        break
                    if rewrite and rewrite.get("status") == "error":
                        break
            if loaded:
                st.rerun()
            else:
                st.warning("Рерайт ещё готовится — нажмите «🔄 Обновить» через пару секунд.")
        except requests.RequestException as e:
            st.error(f"Не удалось запросить рерайт: {e}")
    if gen[1].button("🔄 Обновить"):
        try:
            rewrite = api_get(f"/rewrite/{item_id}")
        except requests.RequestException as e:
            st.error(f"Не удалось получить рерайт: {e}")
            rewrite = None
        if rewrite and rewrite.get("status") == "done" and rewrite.get("text"):
            st.session_state[work_key] = rewrite["text"]
            st.rerun()
        elif rewrite and rewrite.get("status") in ("pending", "processing"):
            st.warning("Рерайт ещё готовится…")
        elif rewrite and rewrite.get("status") == "error":
            st.error("Рерайт не удался.")
        else:
            st.info("Готового рерайта нет — нажмите «Сгенерировать рерайт».")

    # 2. Редактируемый текст — правь вручную.
    edited = st.text_area("Текст статьи (правь вручную)", value=st.session_state[work_key], height=320)
    st.session_state[work_key] = edited

    # 3. Доработка ИИ по указанию редактора.
    st.markdown("**Доработать с ИИ:**")
    instruction = st.text_input(
        "Что поправить",
        placeholder="напр. сократи; перефразируй для уникальности; исправь: губернатор Развожаев",
    )
    ai = st.columns([2, 2, 2, 3])
    if ai[0].button("🔁 Улучшить"):
        if instruction.strip():
            apply_refine(instruction)
        else:
            st.warning("Впишите, что поправить.")
    if ai[1].button("✂️ Короче"):
        apply_refine("Сократи текст, убери лишнее, сохрани факты, цитаты и суть.")
    if ai[2].button("♻️ Уникальнее"):
        apply_refine("Повысь уникальность: перефразируй сильнее, переструктурируй, варьируй длину предложений; сохрани все факты и цитаты.")

    st.divider()

    # 4. Проверки — на ТЕКУЩЕМ (отредактированном) тексте.
    checks = st.columns(2)
    if checks[0].button("🔍 Проверить факты"):
        with st.spinner("Сверяю с первоисточником…"):
            try:
                res = api_post(f"/rewrite/{item_id}/factcheck", json={"text": edited})
                st.session_state[f"fc_{item_id}"] = (res or {}).get("factcheck") or "Фактчек недоступен без ключа LLM."
            except requests.RequestException as e:
                st.error(f"Фактчек не удался: {e}")
    if checks[1].button("📊 Проверить уникальность (до минуты)"):
        with st.spinner("Проверяю уникальность в Text.ru…"):
            try:
                res = api_post(f"/rewrite/{item_id}/uniqueness", json={"text": edited})
                value = (res or {}).get("uniqueness")
                st.session_state[f"uq_{item_id}"] = (
                    f"{value}%" if value is not None
                    else "не проверить (нет ключа Text.ru, текст короткий или не успела)"
                )
            except requests.RequestException as e:
                st.error(f"Проверка уникальности не удалась: {e}")

    factcheck = st.session_state.get(f"fc_{item_id}")
    if factcheck:
        st.markdown("**Проверка фактов:**")
        st.info(factcheck)
        if st.button("🛠 Исправить по фактчеку"):
            apply_refine(f"Исправь фактические расхождения по замечаниям фактчекера: {factcheck}. Остальное сохрани.")
    uniqueness = st.session_state.get(f"uq_{item_id}")
    if uniqueness:
        st.caption(f"Уникальность: {uniqueness}")

    # 5. Готовый текст для публикации — с кнопкой копирования (появляется при наведении).
    if edited.strip():
        st.divider()
        st.markdown("**Готовый текст для публикации:**")
        st.code(edited, language=None)


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

st.set_page_config(page_title="Редакционный радар", page_icon="📡", layout="wide")

# Cookie-менеджер: ДОЖИДАЕМСЯ загрузки cookie из браузера (ready), иначе вход не переживёт F5.
cookies = EncryptedCookieManager(prefix="newsroom/", password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
st.markdown(
    "<div style='padding:0.2rem 0 0.8rem 0'>"
    "<div style='font-size:2.1rem;font-weight:800;letter-spacing:-0.5px'>📡 Редакционный радар</div>"
    "<div style='color:gray;font-size:1rem;margin-top:-2px'>"
    "Приоритизация инфоповодов Севастополя и Крыма — что стоит взять в работу</div>"
    "</div>",
    unsafe_allow_html=True,
)

# Восстанавливаем вход из cookie (переживает перезагрузку страницы F5).
if "token" not in st.session_state:
    st.session_state["token"] = cookies.get("token") or None

# Пока редактор не авторизован — показываем только экран входа.
if not st.session_state.get("token"):
    render_login()
    st.stop()

with st.sidebar:
    st.header("Навигация")
    # Смена раздела закрывает открытую детальную карточку.
    page = st.radio(
        "Раздел", ["Лента", "Источники"], label_visibility="collapsed",
        on_change=lambda: st.session_state.pop("open_item", None),
    )
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

if st.session_state.get("open_item") is not None:
    page_item_detail(st.session_state["open_item"])
elif page == "Лента":
    page_feed()
else:
    page_sources()
