from dotenv import load_dotenv
load_dotenv()

import os
import requests
import streamlit as st

from components.layout import render_sidebar

st.set_page_config(page_title="Настройки", page_icon=":material/settings:", layout="wide")
render_sidebar()

st.title("Настройки")
st.caption("Статус подключений и текущая конфигурация. Значения читаются из .env файла.")


# ── helpers ────────────────────────────────────────────────────────────────────

def mask(value: str | None, show: int = 6) -> str:
    if not value:
        return "—"
    if len(value) <= show:
        return "***"
    return value[:show] + "…" + "*" * 6


def status_badge(ok: bool, ok_text: str = "Подключено", fail_text: str = "Ошибка") -> None:
    if ok:
        st.success(ok_text)
    else:
        st.error(fail_text)


# ── NocoDB ─────────────────────────────────────────────────────────────────────

st.subheader("NocoDB")
col1, col2 = st.columns([1, 1])

NOCODB_URL   = os.getenv("NOCODB_URL", "https://app.nocodb.com")
NOCODB_TOKEN = os.getenv("NOCODB_TOKEN", "")
TABLE_RUNS   = os.getenv("NOCODB_TABLE_SCAN_RUNS", "")
TABLE_FINDS  = os.getenv("NOCODB_TABLE_FINDINGS", "")

with col1:
    st.markdown("**Параметры**")
    st.text(f"URL:            {NOCODB_URL}")
    st.text(f"Token:          {mask(NOCODB_TOKEN)}")
    st.text(f"Table scan_runs:{TABLE_RUNS}")
    st.text(f"Table findings: {TABLE_FINDS}")

with col2:
    st.markdown("**Проверка соединения**")
    if st.button("Проверить NocoDB"):
        try:
            r = requests.get(
                f"{NOCODB_URL}/api/v2/tables/{TABLE_RUNS}/records",
                headers={"xc-token": NOCODB_TOKEN},
                params={"limit": 1},
                timeout=10,
            )
            if r.status_code == 200:
                count = r.json().get("pageInfo", {}).get("totalRows", "?")
                status_badge(True, f"Подключено · scan_runs: {count} записей")
            else:
                status_badge(False, fail_text=f"HTTP {r.status_code}: {r.text[:80]}")
        except Exception as exc:
            status_badge(False, fail_text=str(exc)[:100])

st.divider()

# ── Etherscan ──────────────────────────────────────────────────────────────────

st.subheader("Etherscan API")
col3, col4 = st.columns([1, 1])

ETHERSCAN_KEY     = os.getenv("ETHERSCAN_API_KEY", "")
ETHERSCAN_BASE    = os.getenv("ETHERSCAN_BASE_URL", "https://api.etherscan.io/v2/api")

with col3:
    st.markdown("**Параметры**")
    st.text(f"Base URL:  {ETHERSCAN_BASE}")
    st.text(f"API Key:   {mask(ETHERSCAN_KEY)}")

with col4:
    st.markdown("**Проверка соединения**")
    if st.button("Проверить Etherscan"):
        try:
            r = requests.get(
                ETHERSCAN_BASE,
                params={
                    "chainid": "1",
                    "module":  "stats",
                    "action":  "ethsupply",
                    "apikey":  ETHERSCAN_KEY,
                },
                timeout=10,
            )
            data = r.json()
            if data.get("status") == "1":
                status_badge(True, "Подключено · API-ключ действителен")
            else:
                status_badge(False, fail_text=data.get("message", "Ошибка API"))
        except Exception as exc:
            status_badge(False, fail_text=str(exc)[:100])

st.divider()

# ── OpenRouter / LLM ───────────────────────────────────────────────────────────

st.subheader("LLM (OpenRouter)")
col5, col6 = st.columns([1, 1])

OR_KEY      = os.getenv("OPENROUTER_API_KEY", "")
OR_MODEL    = os.getenv("OPENROUTER_MODEL", "не задан")
OR_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

with col5:
    st.markdown("**Параметры**")
    st.text(f"Base URL: {OR_BASE_URL}")
    st.text(f"API Key:  {mask(OR_KEY)}")
    st.text(f"Модель:   {OR_MODEL}")

with col6:
    st.markdown("**Проверка соединения**")
    if st.button("Проверить OpenRouter"):
        try:
            r = requests.post(
                f"{OR_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"},
                json={
                    "model": OR_MODEL,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 3,
                },
                timeout=20,
            )
            if r.status_code == 200:
                model_used = r.json().get("model", OR_MODEL)
                status_badge(True, f"Подключено · модель: {model_used}")
            else:
                status_badge(False, fail_text=f"HTTP {r.status_code}: {r.text[:120]}")
        except Exception as exc:
            status_badge(False, fail_text=str(exc)[:100])

    st.markdown("**Доступные бесплатные модели**")
    if st.button("Показать список"):
        try:
            r = requests.get(
                f"{OR_BASE_URL}/models",
                headers={"Authorization": f"Bearer {OR_KEY}"},
                timeout=10,
            )
            models = [m["id"] for m in r.json().get("data", []) if ":free" in m.get("id", "")]
            st.code("\n".join(sorted(models)))
        except Exception as exc:
            st.error(str(exc))

st.divider()

# ── Анализаторы ────────────────────────────────────────────────────────────────

st.subheader("Статические анализаторы")

import shutil

tools = {
    "Slither":  ("slither",  "pip install slither-analyzer"),
    "Mythril":  ("myth",     "pip install mythril"),
    "Semgrep":  ("semgrep",  "pip install semgrep"),
}

tc = st.columns(len(tools))
for i, (name, (cmd, install)) in enumerate(tools.items()):
    path = shutil.which(cmd)
    with tc[i]:
        st.markdown(f"**{name}**")
        if path:
            st.success("найден")
            st.caption(path)
        else:
            st.error("не найден")
            st.caption(f"`{install}`")

mythril_bin = os.getenv("MYTHRIL_BIN", "")
if mythril_bin:
    st.caption(f"MYTHRIL_BIN override: `{mythril_bin}`")

st.divider()

# ── .env справка ───────────────────────────────────────────────────────────────

with st.expander("Шаблон .env файла"):
    st.code(
        """NOCODB_URL=https://app.nocodb.com
NOCODB_TOKEN=your_token_here
NOCODB_TABLE_SCAN_RUNS=your_table_id
NOCODB_TABLE_FINDINGS=your_table_id
NOCODB_TABLE_TOOLS=your_table_id
NOCODB_TABLE_CONTRACTS=your_table_id

ETHERSCAN_API_KEY=your_api_key
ETHERSCAN_BASE_URL=https://api.etherscan.io/v2/api

OPENROUTER_API_KEY=your_api_key
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

MYTHRIL_BIN=/path/to/myth   # опционально
""",
        language="bash",
    )