from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import streamlit as st

from components.layout import render_sidebar

st.set_page_config(page_title="История запусков", page_icon=":material/history:", layout="wide")
render_sidebar()

st.title("История запусков")
st.caption("Все проверенные контракты. Выбери строку — увидишь подробности и findings.")

# ── загрузка ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_runs():
    try:
        from connectors.nocodb_client import get_all_runs
        rows = get_all_runs(limit=200)
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as exc:
        st.error(f"Ошибка загрузки: {exc}")
        return pd.DataFrame()


@st.cache_data(ttl=30)
def load_findings(run_id: int):
    try:
        from connectors.nocodb_client import get_findings_for_run
        rows = get_findings_for_run(run_id)
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as exc:
        return pd.DataFrame()


runs = load_runs()

if runs.empty:
    st.warning("История пока пуста. Запусти хотя бы один анализ на главной странице.")
    st.stop()

# ── подготовка таблицы ─────────────────────────────────────────────────────────

runs["CreatedAt"] = pd.to_datetime(runs["CreatedAt"], errors="coerce", utc=True)
runs["Дата"] = runs["CreatedAt"].dt.strftime("%Y-%m-%d %H:%M")
runs["risk_score"] = pd.to_numeric(runs["risk_score"], errors="coerce").fillna(0).astype(int)

SHOW_COLS = {
    "contract_name":    "Контракт",
    "address":          "Адрес",
    "network":          "Сеть",
    "overall_verdict":  "Вердикт",
    "risk_score":       "Risk score",
    "tools_used":       "Инструменты",
    "analyst":          "Аналитик",
    "Дата":             "Дата",
}
existing = {k: v for k, v in SHOW_COLS.items() if k in runs.columns}
display_df = runs[list(existing.keys())].rename(columns=existing).reset_index(drop=True)

# ── фильтры ────────────────────────────────────────────────────────────────────

fc1, fc2, fc3 = st.columns(3)
with fc1:
    flt_verdict = st.multiselect("Вердикт", ["trusted", "warning", "suspicious"])
with fc2:
    flt_analyst = st.text_input("Аналитик", placeholder="фильтр по имени")
with fc3:
    flt_network = st.multiselect("Сеть", sorted(runs["network"].dropna().unique().tolist()))

mask = pd.Series([True] * len(display_df))
if flt_verdict:
    mask &= runs["overall_verdict"].isin(flt_verdict)
if flt_analyst:
    mask &= runs["analyst"].str.contains(flt_analyst, case=False, na=False)
if flt_network:
    mask &= runs["network"].isin(flt_network)

filtered_display = display_df[mask].reset_index(drop=True)
filtered_runs    = runs[mask].reset_index(drop=True)

st.caption(f"Показано: {len(filtered_display)} из {len(runs)}")

# ── таблица с выбором строки ───────────────────────────────────────────────────

selected = st.dataframe(
    filtered_display,
    use_container_width=True,
    selection_mode="single-row",
    on_select="rerun",
    hide_index=True,
)

# ── детальный просмотр ─────────────────────────────────────────────────────────

sel_rows = selected.selection.rows if selected and selected.selection else []

if sel_rows:
    idx = sel_rows[0]
    run_row = filtered_runs.iloc[idx]
    run_id  = int(run_row["Id"])

    st.divider()

    # Заголовок
    verdict = run_row.get("overall_verdict", "")
    st.subheader(f"{run_row.get('contract_name', '—')} · risk score {int(run_row.get('risk_score', 0))}")

    # Метрики
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Адрес",     run_row.get("address", "—")[:20] + "…")
    mc2.metric("Сеть",      run_row.get("network", "—"))
    mc3.metric("Вердикт",   verdict)
    mc4.metric("Аналитик",  run_row.get("analyst", "—"))

    mc5, mc6, mc7 = st.columns(3)
    mc5.metric("Инструменты",  run_row.get("tools_used", "—"))
    mc6.metric("Статус",       run_row.get("status", "—"))
    mc7.metric("Дата",         str(run_row.get("Дата", "—")))

    # Findings
    st.subheader("Findings")
    findings_df = load_findings(run_id)

    if findings_df.empty:
        st.info("Findings для этого запуска не сохранены.")
    else:
        # Сводка по severity
        if "severity_label" in findings_df.columns:
            SEV_ORDER  = ["critical", "high", "medium", "low", "info"]
            sev_counts = findings_df["severity_label"].value_counts()

            sc = st.columns(len(SEV_ORDER))
            for i, sev in enumerate(SEV_ORDER):
                sc[i].metric(sev.capitalize(), sev_counts.get(sev, 0))

        # Таблица findings
        FIND_COLS = {
            "tool":             "Инструмент",
            "rule_id":          "Rule ID",
            "title":            "Заголовок",
            "severity_label":   "Severity",
            "confidence_label": "Confidence",
            "category":         "Категория",
            "description":      "Описание",
            "recommendation":   "Рекомендация",
            "file_path":        "Файл",
            "line_start":       "Строка",
        }
        f_existing = {k: v for k, v in FIND_COLS.items() if k in findings_df.columns}
        st.dataframe(
            findings_df[list(f_existing.keys())].rename(columns=f_existing),
            use_container_width=True,
            hide_index=True,
        )

        # Детальный просмотр каждого finding
        with st.expander("Подробное описание каждой находки"):
            for _, f in findings_df.iterrows():
                sev = f.get("severity_label", "info")
                st.markdown(f"#### {f.get('title', '—')}")
                cols = st.columns(3)
                cols[0].write(f"**Инструмент:** {f.get('tool','—')}")
                cols[1].write(f"**Severity:** {sev}")
                cols[2].write(f"**Rule ID:** {f.get('rule_id','—')}")
                if f.get("description"):
                    st.write(f"**Описание:** {f.get('description')}")
                if f.get("recommendation"):
                    st.write(f"**Рекомендация:** {f.get('recommendation')}")
                st.divider()

    # Экспорт
    st.subheader("Экспорт")
    ex1, ex2, ex3 = st.columns(3)

    with ex1:
        if not findings_df.empty:
            csv = findings_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Скачать findings (CSV)",
                data=csv,
                file_name=f"findings_{run_row.get('contract_name','run')}_{run_id}.csv",
                mime="text/csv",
            )

    with ex2:
        import json
        summary_export = {
            "run_id":          run_id,
            "contract_name":   run_row.get("contract_name"),
            "address":         run_row.get("address"),
            "network":         run_row.get("network"),
            "overall_verdict": run_row.get("overall_verdict"),
            "risk_score":      int(run_row.get("risk_score", 0)),
            "analyst":         run_row.get("analyst"),
            "date":            str(run_row.get("Дата")),
            "findings":        findings_df.to_dict(orient="records") if not findings_df.empty else [],
        }
        st.download_button(
            label="Скачать отчёт (JSON)",
            data=json.dumps(summary_export, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"report_{run_row.get('contract_name','run')}_{run_id}.json",
            mime="application/json",
        )

    with ex3:
        try:
            from services.pdf_report import generate_pdf_report
            findings_for_pdf = findings_df.to_dict(orient="records") if not findings_df.empty else []
            pdf_bytes = generate_pdf_report(
                contract_name=run_row.get("contract_name", "—"),
                address=run_row.get("address", "—"),
                network=run_row.get("network", "—"),
                verdict=run_row.get("overall_verdict", "—"),
                risk_score=int(run_row.get("risk_score", 0)),
                analyst=run_row.get("analyst", "—"),
                summary=run_row.get("summary", ""),
                findings=findings_for_pdf,
                tools_used=run_row.get("tools_used", ""),
                date=str(run_row.get("Дата", "")),
            )
            st.download_button(
                label="Скачать отчёт (PDF)",
                data=pdf_bytes,
                file_name=f"report_{run_row.get('contract_name','run')}_{run_id}.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.error(f"PDF недоступен: {e}")

else:
    st.caption("Кликни на строку в таблице выше, чтобы увидеть подробности.")

if st.button("Обновить"):
    st.cache_data.clear()
    st.rerun()