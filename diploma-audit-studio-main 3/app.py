from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import streamlit as st

from components.layout import render_sidebar, inject_css
from services.nocodb_service import check_nocodb_config, get_recent_runs
from services.etherscan_service import get_contract_metadata
from services.scanner_service import run_scan, find_cached_result

st.set_page_config(
    page_title="Smart Contract Audit Studio",
    page_icon=":material/shield:",
    layout="wide",
)

inject_css()
render_sidebar()

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div>
        <div class="hero-title">Smart Contract Audit Studio</div>
        <div class="hero-sub">Автоматический анализ смарт-контрактов: Slither · Mythril · LLM</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Функция рендера результата (определяем до вызова) ─────────────────────────
def _render_result(scan_result, etherscan_info, source_code, contract_name):
    risk_score = scan_result.get("risk_score", 0)
    # Prefer LLM verdict string; fall back to trust_flag → derive verdict from score
    _llm_verdict = (scan_result.get("llm_summary") or {}).get("overall_verdict")
    if _llm_verdict:
        verdict = str(_llm_verdict).lower()
    else:
        trust_flag = scan_result.get("trust_flag", 0)
        if trust_flag == 1 or risk_score < 20:
            verdict = "trusted"
        elif risk_score < 50:
            verdict = "warning"
        else:
            verdict = "suspicious"
    llm_sum    = scan_result.get("llm_summary") or {}
    findings   = scan_result.get("findings", [])
    sev_counts = scan_result.get("severity_counts", {})

    # Verdict banner
    VERDICT_CSS = {
        "trusted":    ("verdict-trusted",    "Trusted"),
        "warning":    ("verdict-warning",    "Warning"),
        "suspicious": ("verdict-suspicious", "Suspicious"),
    }
    css_class, label = VERDICT_CSS.get(str(verdict).lower(), ("verdict-unknown", str(verdict).upper() if verdict is not None else "N/A"))

    st.markdown(f"""
    <div class="verdict-banner {css_class}">
        <div class="verdict-label">{label}</div>
        <div class="verdict-risk">{risk_score}<span style="font-size:0.55em;font-weight:500;opacity:0.65;margin-left:4px;font-family:Roboto,sans-serif">/ 100</span></div>
    </div>
    """, unsafe_allow_html=True)

    # LLM summary
    if llm_sum.get("summary"):
        st.markdown("#### LLM Review")
        st.write(llm_sum["summary"])

    # Severity metrics
    st.markdown("#### Находки по severity")
    mc = st.columns(5)
    for i, sev in enumerate(["critical", "high", "medium", "low", "info"]):
        mc[i].metric(sev.capitalize(), sev_counts.get(sev, 0))

    tools_used = scan_result.get("tools_used", [])
    tc1, tc2 = st.columns(2)
    tc1.metric("Инструменты", " + ".join(tools_used) if tools_used else "—")
    tc2.metric("Всего находок", len(findings))

    # Tool errors
    tool_errors = scan_result.get("tool_errors", [])
    if tool_errors:
        with st.expander(f"Ошибки анализаторов ({len(tool_errors)})"):
            for e in tool_errors:
                st.warning(f"**{e.get('tool')}**: {e.get('error','')[:300]}")

    # Findings table
    if findings:
        st.markdown("#### Детальные находки")

        SEV_ORDER = ["critical", "high", "medium", "low", "info"]
        SEV_DOT   = {
            "critical": "oklch(50% 0.17 25)",
            "high":     "oklch(60% 0.14 48)",
            "medium":   "oklch(68% 0.13 78)",
            "low":      "oklch(52% 0.12 240)",
            "info":     "oklch(62% 0.04 200)",
        }

        for sev in SEV_ORDER:
            group = [f for f in findings if f.get("severity") == sev or f.get("severity_label") == sev]
            if not group:
                continue
            dot = f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:{SEV_DOT.get(sev,"#999")};margin-right:7px;vertical-align:middle;"></span>'
            st.markdown(f"**{dot}{sev.upper()} — {len(group)} шт.**", unsafe_allow_html=True)
            for f in group:
                with st.expander(f"{f.get('title') or f.get('rule_id','—')}  ·  {f.get('tool','—')}"):
                    cols = st.columns(3)
                    cols[0].write(f"**Rule:** `{f.get('rule_id','—')}`")
                    cols[1].write(f"**Confidence:** {f.get('confidence','—')}")
                    cols[2].write(f"**Category:** {f.get('category','—')}")
                    if f.get("file_path"):
                        loc = f["file_path"]
                        if f.get("line_start"):
                            loc += f":{f['line_start']}"
                            if f.get("line_end") and f["line_end"] != f["line_start"]:
                                loc += f"–{f['line_end']}"
                        st.caption(f"Файл: {loc}")
                    if f.get("description"):
                        st.write(f.get("description"))
                    if f.get("recommendation"):
                        st.info(f"**Рекомендация:** {f.get('recommendation')}")

    # Экспорт
    st.markdown("#### Экспорт")
    ex1, ex2, ex3 = st.columns(3)

    findings_df = pd.DataFrame(findings) if findings else pd.DataFrame()

    with ex1:
        if not findings_df.empty:
            st.download_button(
                "Скачать CSV",
                data=findings_df.to_csv(index=False).encode("utf-8"),
                file_name=f"findings_{contract_name}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with ex2:
        import json
        st.download_button(
            "Скачать JSON",
            data=json.dumps(scan_result, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
            file_name=f"report_{contract_name}.json",
            mime="application/json",
            use_container_width=True,
        )

    with ex3:
        try:
            from services.pdf_report import generate_pdf_report
            pdf_bytes = generate_pdf_report(
                contract_name=contract_name or "—",
                address=scan_result.get("address", "—"),
                network=scan_result.get("network", "—"),
                verdict=str(verdict),
                risk_score=risk_score,
                analyst=scan_result.get("analyst", "—"),
                summary=llm_sum.get("summary", ""),
                findings=findings_df.to_dict(orient="records") if not findings_df.empty else findings,
                tools_used=",".join(tools_used),
            )
            st.download_button(
                "Скачать PDF",
                data=pdf_bytes,
                file_name=f"report_{contract_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"PDF: {e}")

    # Исходник и raw
    if etherscan_info and etherscan_info.get("ok"):
        with st.expander("Метаданные Etherscan"):
            st.json({k: v for k, v in etherscan_info.items() if k != "source_code"})

    if source_code:
        with st.expander("Исходный код контракта"):
            st.code(source_code[:8000], language="solidity")

    with st.expander("Raw JSON результата"):
        st.json(scan_result)


# ── Layout ────────────────────────────────────────────────────────────────────
col_form, col_side = st.columns([1.4, 1], gap="large")

with col_form:
    st.markdown("#### Новый анализ")

    with st.form("scan_form"):
        r1c1, r1c2 = st.columns([2, 1])
        with r1c1:
            contract_address = st.text_input(
                "Адрес контракта",
                placeholder="0x…",
                help="Etherscan вернёт исходный код для верифицированных контрактов.",
            )
        with r1c2:
            chain = st.selectbox("Сеть", ["Ethereum", "Base", "BSC", "Arbitrum"])

        project_name = st.text_input("Название проекта (опционально)", placeholder="My audit")

        with st.expander("Исходный код вручную (если нет Etherscan)"):
            uploaded_file = st.file_uploader("Загрузить .sol файл", type=["sol"])
            source_code_text = st.text_area(
                "Или вставь код",
                height=200,
                placeholder="pragma solidity ^0.8.0;\n\ncontract MyContract { … }",
            )

        st.markdown("**Анализаторы**")
        ac1, ac2, ac3, ac4 = st.columns(4)
        with ac1:
            use_slither  = st.checkbox("Slither",     value=True)
        with ac2:
            use_mythril  = st.checkbox("Mythril",     value=True)
        with ac3:
            use_llm      = st.checkbox("LLM review",  value=True)
        with ac4:
            use_semgrep  = st.checkbox("Semgrep",     value=False)

        st.markdown("**Параметры**")
        oc1, oc2, oc3 = st.columns(3)
        with oc1:
            use_etherscan  = st.checkbox("Получить код через Etherscan", value=True)
        with oc2:
            save_to_nocodb = st.checkbox("Сохранить в NocoDB", value=True)
        with oc3:
            force_rerun    = st.checkbox("Игнорировать кеш", value=False)

        submitted = st.form_submit_button(
            "Запустить анализ", use_container_width=True, type="primary",
        )

    # ── Результат ─────────────────────────────────────────────────────────────
    if submitted:
        source_code    = None
        contract_name  = contract_address
        etherscan_info = None
        scan_result    = None

        if not contract_address and not source_code_text.strip() and uploaded_file is None:
            st.error("Введи адрес контракта или вставь исходный код.")
            st.stop()

        if not any([use_slither, use_mythril, use_semgrep, use_llm]):
            st.error("Выбери хотя бы один анализатор.")
            st.stop()

        # 1. Кеш
        if save_to_nocodb and not force_rerun and contract_address:
            with st.spinner("Проверяю кеш…"):
                scan_result = find_cached_result(contract_address, chain.lower())
            if scan_result:
                scan_result["from_cache"] = True
                st.info(
                    f"Результат из кеша ({scan_result.get('cached_at','')[:10]}). "
                    "Поставь «Игнорировать кеш» для повторного анализа."
                )

        # 2. Полный анализ
        if scan_result is None:
            if use_etherscan and contract_address:
                with st.spinner("Получаю исходный код через Etherscan…"):
                    etherscan_info = get_contract_metadata(contract_address, network=chain.lower())
                if etherscan_info.get("ok"):
                    source_code   = etherscan_info.get("source_code")
                    contract_name = etherscan_info.get("contract_name") or contract_address
                    st.success(f"Код получен: **{contract_name}**")
                else:
                    st.warning(f"Etherscan: {etherscan_info.get('error','unknown error')}")

            if not source_code and uploaded_file is not None:
                try:
                    source_code = uploaded_file.read().decode("utf-8")
                    st.info("Используется загруженный .sol файл.")
                except UnicodeDecodeError:
                    st.error("Не удалось прочитать .sol файл как UTF-8.")
                    st.stop()

            if not source_code and source_code_text.strip():
                source_code = source_code_text.strip()
                st.info("Используется код, вставленный вручную.")

            if not source_code:
                st.error("Не удалось получить исходный код.")
                st.stop()

            with st.spinner("Запускаю анализ… (Slither + Mythril + LLM могут занять 1-2 мин)"):
                scan_result = run_scan(
                    address=contract_address or "0x0000000000000000000000000000000000000000",
                    network=chain.lower(),
                    options={
                        "project_name": project_name,
                        "slither": use_slither,
                        "mythril": use_mythril,
                        "semgrep": use_semgrep,
                        "llm": use_llm,
                        "source_code": source_code,
                        "contract_name": contract_name,
                        "etherscan_metadata": etherscan_info or {},
                    },
                    save_to_nocodb=save_to_nocodb,
                    analyst=st.session_state.get("analyst", ""),
                )

        # 3. Отображение результата
        _render_result(scan_result, etherscan_info, source_code, contract_name)


# ── Боковая панель (правая) ───────────────────────────────────────────────────
with col_side:
    # Статус интеграций
    st.markdown("#### Интеграции")
    nocodb_status = check_nocodb_config()
    if "OK" in str(nocodb_status):
        st.success(f"NocoDB: подключён")
    else:
        st.warning(f"NocoDB: {nocodb_status}")

    import shutil, os
    for name, cmd in [("Slither", "slither"), ("Mythril", "myth")]:
        found = shutil.which(cmd) or (
            name == "Mythril" and os.path.isfile(os.getenv("MYTHRIL_BIN", "") or "")
        )
        ok_style  = "background:oklch(92% 0.06 150);color:oklch(26% 0.10 150)"
        err_style = "background:oklch(91% 0.07 20);color:oklch(28% 0.12 20)"
        badge = f'<span style="font-size:0.7rem;font-weight:600;padding:1px 7px;border-radius:4px;{ok_style if found else err_style}">{"OK" if found else "—"}</span>'
        st.markdown(f'{badge} {name}', unsafe_allow_html=True)
    ok_style = "background:oklch(92% 0.06 150);color:oklch(26% 0.10 150)"
    st.markdown(f'<span style="font-size:0.7rem;font-weight:600;padding:1px 7px;border-radius:4px;{ok_style}">OK</span> LLM (OpenRouter)', unsafe_allow_html=True)

    # Последние запуски
    st.markdown("#### Последние запуски")
    recent_runs = get_recent_runs(limit=8)
    if recent_runs.empty:
        st.caption("Пока пусто.")
    else:
        VERDICT_DOT = {
            "trusted":    "oklch(42% 0.13 150)",
            "warning":    "oklch(55% 0.13 76)",
            "suspicious": "oklch(50% 0.16 20)",
        }
        for _, row in recent_runs.iterrows():
            v     = str(row.get("overall_verdict", "")).lower()
            color = VERDICT_DOT.get(v, "oklch(70% 0.005 55)")
            dot   = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:7px;vertical-align:middle;flex-shrink:0"></span>'
            name  = row.get("contract_name", row.get("address", "—"))[:22]
            score = row.get("risk_score", "—")
            st.markdown(f'{dot}**{name}** · risk {score}', unsafe_allow_html=True)

    # Как это работает
    st.markdown("#### Как это работает")
    st.markdown("""
1. **Etherscan** — получает верифицированный исходный код
2. **Кеш** — если адрес уже анализировался, возвращает результат мгновенно
3. **Slither** — статический анализ: reentrancy, overflow, права доступа
4. **Mythril** — символьное исполнение: SWC-107, SWC-105 и др.
5. **LLM** — семантический разбор: honeypot-паттерны, rug pull, blacklist
""")
