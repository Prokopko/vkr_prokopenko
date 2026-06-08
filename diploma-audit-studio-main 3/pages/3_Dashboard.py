from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.layout import render_sidebar

st.set_page_config(
    page_title="Дашборд",
    page_icon=":material/bar_chart:",
    layout="wide",
)

render_sidebar()
st.title("Дашборд аудитора")
st.caption("Сводная аналитика по всем проверенным смарт-контрактам")

# ── загрузка данных ────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_data():
    try:
        from connectors.nocodb_client import get_all_runs, get_all_findings
        runs = pd.DataFrame(get_all_runs(limit=500))
        findings = pd.DataFrame(get_all_findings(limit=2000))
        return runs, findings
    except Exception as exc:
        st.error(f"Ошибка загрузки данных из NocoDB: {exc}")
        return pd.DataFrame(), pd.DataFrame()


runs, findings = load_data()

if runs.empty:
    st.warning("Данных пока нет. Запусти хотя бы один анализ на главной странице.")
    st.stop()

# ── подготовка ─────────────────────────────────────────────────────────────────

runs["CreatedAt"] = pd.to_datetime(runs["CreatedAt"], errors="coerce", utc=True)
runs["date"] = runs["CreatedAt"].dt.date
runs["risk_score"] = pd.to_numeric(runs["risk_score"], errors="coerce").fillna(0)

VERDICT_COLORS = {
    "trusted":    "#d4b896",
    "warning":    "#cc6a0a",
    "suspicious": "#7a3000",
    "":           "#c4b0a0",
}

SEV_ORDER = ["critical", "high", "medium", "low", "info"]
SEV_COLORS = {
    "critical": "#7a2800",
    "high":     "#b04800",
    "medium":   "#cc6a0a",
    "low":      "#d4a060",
    "info":     "#c8b498",
}

# ── топ-метрики ────────────────────────────────────────────────────────────────

total       = len(runs)
suspicious  = (runs["overall_verdict"] == "suspicious").sum()
warning     = (runs["overall_verdict"] == "warning").sum()
trusted     = (runs["overall_verdict"] == "trusted").sum()
avg_risk    = runs["risk_score"].mean()
total_finds = len(findings)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Всего проверено",   total)
c2.metric("Подозрительных",    suspicious, delta=f"{suspicious/total*100:.0f}%" if total else None, delta_color="inverse")
c3.metric("Требуют внимания",  warning)
c4.metric("Надёжных",          trusted)
c5.metric("Средний risk score", f"{avg_risk:.0f}")

st.divider()

# ── ряд 1: вердикты + severity ─────────────────────────────────────────────────

row1_left, row1_right = st.columns(2)

with row1_left:
    st.subheader("Распределение вердиктов")
    verdict_counts = runs["overall_verdict"].fillna("неизвестно").value_counts().reset_index()
    verdict_counts.columns = ["verdict", "count"]
    verdict_counts["color"] = verdict_counts["verdict"].map(VERDICT_COLORS).fillna("#95a5a6")

    fig_pie = px.pie(
        verdict_counts,
        names="verdict",
        values="count",
        color="verdict",
        color_discrete_map=VERDICT_COLORS,
        hole=0.4,
    )
    fig_pie.update_traces(textinfo="label+percent", textfont_size=13)
    fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300)
    st.plotly_chart(fig_pie, use_container_width=True)

with row1_right:
    st.subheader("Severity всех находок")
    if not findings.empty and "severity_label" in findings.columns:
        sev_counts = (
            findings["severity_label"]
            .fillna("info")
            .value_counts()
            .reindex(SEV_ORDER, fill_value=0)
            .reset_index()
        )
        sev_counts.columns = ["severity", "count"]
        sev_counts["color"] = sev_counts["severity"].map(SEV_COLORS)

        fig_sev = px.bar(
            sev_counts,
            x="severity", y="count",
            color="severity",
            color_discrete_map=SEV_COLORS,
            text="count",
        )
        fig_sev.update_traces(textposition="outside")
        fig_sev.update_layout(
            showlegend=False,
            xaxis_title=None, yaxis_title="Количество",
            margin=dict(t=10, b=10, l=10, r=10),
            height=300,
        )
        st.plotly_chart(fig_sev, use_container_width=True)
    else:
        st.info("Findings ещё нет.")

# ── ряд 2: топ уязвимостей + timeline ─────────────────────────────────────────

row2_left, row2_right = st.columns(2)

with row2_left:
    st.subheader("Топ уязвимостей")
    if not findings.empty and "rule_id" in findings.columns:
        top_rules = (
            findings[findings["rule_id"].notna() & (findings["rule_id"] != "")]
            .groupby(["rule_id", "severity_label"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(10)
        )
        top_rules["color"] = top_rules["severity_label"].map(SEV_COLORS).fillna("#95a5a6")

        fig_rules = px.bar(
            top_rules,
            x="count", y="rule_id",
            orientation="h",
            color="severity_label",
            color_discrete_map=SEV_COLORS,
            text="count",
        )
        fig_rules.update_traces(textposition="outside")
        fig_rules.update_layout(
            showlegend=True,
            legend_title="Severity",
            xaxis_title="Количество", yaxis_title=None,
            yaxis={"categoryorder": "total ascending"},
            margin=dict(t=10, b=10, l=10, r=10),
            height=350,
        )
        st.plotly_chart(fig_rules, use_container_width=True)
    else:
        st.info("Findings ещё нет.")

with row2_right:
    st.subheader("Активность по дням")
    if "date" in runs.columns:
        timeline = (
            runs.groupby(["date", "overall_verdict"])
            .size()
            .reset_index(name="count")
        )
        if not timeline.empty:
            fig_time = px.bar(
                timeline,
                x="date", y="count",
                color="overall_verdict",
                color_discrete_map=VERDICT_COLORS,
                barmode="stack",
            )
            fig_time.update_layout(
                xaxis_title=None, yaxis_title="Кол-во анализов",
                legend_title="Вердикт",
                margin=dict(t=10, b=10, l=10, r=10),
                height=350,
            )
            st.plotly_chart(fig_time, use_container_width=True)

# ── ряд 3: риск по инструментам + таблица контрактов ─────────────────────────

row3_left, row3_right = st.columns([1, 1.6])

with row3_left:
    st.subheader("Находки по инструментам")
    if not findings.empty and "tool" in findings.columns:
        tool_counts = (
            findings.groupby(["tool", "severity_label"])
            .size()
            .reset_index(name="count")
        )
        fig_tools = px.bar(
            tool_counts,
            x="tool", y="count",
            color="severity_label",
            color_discrete_map=SEV_COLORS,
            barmode="stack",
            text_auto=True,
        )
        fig_tools.update_layout(
            xaxis_title=None, yaxis_title="Находок",
            legend_title="Severity",
            margin=dict(t=10, b=10, l=10, r=10),
            height=320,
        )
        st.plotly_chart(fig_tools, use_container_width=True)

with row3_right:
    st.subheader("Самые опасные контракты")
    danger = (
        runs[runs["overall_verdict"].isin(["suspicious", "warning"])]
        .sort_values("risk_score", ascending=False)
        [["contract_name", "address", "network", "overall_verdict", "risk_score", "tools_used", "analyst"]]
        .head(15)
    )
    if not danger.empty:
        def color_verdict(val):
            colors = {"suspicious": "background-color:#fdd;color:#900",
                      "warning":    "background-color:#ffe;color:#850"}
            return colors.get(val, "")

        styled = danger.style.map(color_verdict, subset=["overall_verdict"])
        st.dataframe(styled, use_container_width=True, height=320)
    else:
        st.info("Подозрительных контрактов пока нет.")

# ── ряд 4: полная история ─────────────────────────────────────────────────────

st.divider()
st.subheader("Все проверенные контракты")

col_filter1, col_filter2, col_filter3 = st.columns(3)
with col_filter1:
    filter_verdict = st.multiselect(
        "Фильтр по вердикту",
        options=["trusted", "warning", "suspicious"],
        default=[],
    )
with col_filter2:
    filter_analyst = st.text_input("Фильтр по аналитику", placeholder="имя аналитика")
with col_filter3:
    filter_network = st.multiselect(
        "Сеть",
        options=sorted(runs["network"].dropna().unique().tolist()),
        default=[],
    )

filtered = runs.copy()
if filter_verdict:
    filtered = filtered[filtered["overall_verdict"].isin(filter_verdict)]
if filter_analyst:
    filtered = filtered[filtered["analyst"].str.contains(filter_analyst, case=False, na=False)]
if filter_network:
    filtered = filtered[filtered["network"].isin(filter_network)]

display_cols = ["contract_name", "address", "network", "overall_verdict",
                "risk_score", "tools_used", "analyst", "date"]
existing = [c for c in display_cols if c in filtered.columns]
st.dataframe(filtered[existing].reset_index(drop=True), use_container_width=True)

if st.button("Обновить данные"):
    st.cache_data.clear()
    st.rerun()