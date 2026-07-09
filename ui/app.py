"""Витрина редактора. На шаге 0 — проверка связи с API; лента добавляется дальше."""
import os

import requests
import streamlit as st

# Адрес API внутри docker-сети (имя сервиса из docker-compose).
API_URL = os.environ.get("API_URL", "http://api:8000")

st.set_page_config(page_title="Newsroom Prioritizer", page_icon="📰")
st.title("📰 Newsroom Prioritizer")
st.caption("Приоритизация инфоповодов редакции")

# Проверяем доступность бэкенда — на старте это единственная функция витрины.
try:
    resp = requests.get(f"{API_URL}/health", timeout=5)
    if resp.ok and resp.json().get("status") == "ok":
        st.success("API доступен — связь есть.")
    else:
        st.warning(f"API ответил неожиданно: {resp.status_code}")
except requests.RequestException as e:
    st.error(f"API недоступен: {e}")

st.info("Лента инфоповодов появится на следующих шагах сборки.")
