import streamlit as st


def inject_css() -> None:
    st.markdown("""
<style>
/* ── Fonts ──────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,400;0,500&family=Roboto:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Roboto', sans-serif;
}

/* ── Headings ───────────────────────────────────────────────────── */
h1 { font-size: 2.5rem !important; font-weight: 700 !important; letter-spacing: -0.03em !important; line-height: 1.1 !important; }
h2 { font-size: 1.85rem !important; font-weight: 700 !important; letter-spacing: -0.025em !important; line-height: 1.15 !important; }
h3 { font-size: 1.35rem !important; font-weight: 600 !important; letter-spacing: -0.015em !important; }
h4 { font-size: 1.05rem !important; font-weight: 600 !important; }

/* ── Hero ───────────────────────────────────────────────────────── */
.hero {
    padding: 8px 0 20px;
    margin-bottom: 28px;
    border-bottom: 1.5px solid oklch(88% 0.008 55);
}
.hero-icon  { display: none; }
.hero-title {
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: oklch(18% 0.012 55);
    line-height: 1.1;
}
.hero-sub {
    font-size: 0.82rem;
    color: oklch(52% 0.010 55);
    margin-top: 6px;
    font-family: 'DM Mono', monospace;
    letter-spacing: 0.01em;
}

/* ── Cards ──────────────────────────────────────────────────────── */
.card {
    background: oklch(99.2% 0.004 55);
    border: 1px solid oklch(90% 0.008 55);
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
}

/* ── Verdict banners ─────────────────────────────────────────────── */
.verdict-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-radius: 8px;
    padding: 14px 22px;
    margin: 16px 0;
}
.verdict-label {
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.verdict-risk {
    font-size: 1.8rem;
    font-weight: 700;
    font-family: 'DM Mono', monospace;
    font-variant-numeric: tabular-nums;
    line-height: 1;
}

.verdict-trusted    { background: oklch(92% 0.06 150); color: oklch(26% 0.10 150); }
.verdict-warning    { background: oklch(92% 0.07 76);  color: oklch(28% 0.09 62);  }
.verdict-suspicious { background: oklch(91% 0.07 20);  color: oklch(28% 0.12 20);  }
.verdict-unknown    { background: oklch(94% 0.005 55); color: oklch(42% 0.008 55); }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    border-right: 1px solid oklch(88% 0.008 55) !important;
}
[data-testid="stSidebarNav"] {
    display: none !important;
}
[data-testid="stSidebar"] * {
    color: oklch(18% 0.012 55) !important;
}
[data-testid="stSidebar"] a:hover {
    background: oklch(90% 0.010 55) !important;
    border-radius: 6px !important;
}

/* ── Primary button ─────────────────────────────────────────────── */
[data-testid="stFormSubmitButton"] > button {
    background: oklch(58% 0.18 50) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    letter-spacing: 0.025em !important;
    padding: 10px 20px !important;
    transition: background 0.15s ease !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    background: oklch(50% 0.18 50) !important;
    opacity: 1 !important;
}

/* ── Metrics ─────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: oklch(97% 0.008 55);
    border: 1px solid oklch(91% 0.008 55);
    border-radius: 8px;
    padding: 10px 14px;
}

/* ── Mono for technical text ─────────────────────────────────────── */
input[placeholder*="0x"],
[data-testid="stCodeBlock"],
pre, code {
    font-family: 'DM Mono', monospace !important;
}

/* ── Hero subtitle font ──────────────────────────────────────────── */
.hero-sub, .hero-title {
    font-family: 'Roboto', sans-serif;
}
</style>
""", unsafe_allow_html=True)


def render_sidebar() -> None:
    inject_css()
    with st.sidebar:
        st.markdown("""
<div style="padding: 20px 16px 12px;">
    <div style="font-size: 0.62rem; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: oklch(54% 0.008 55); margin-bottom: 3px;">Smart Contract</div>
    <div style="font-size: 1.05rem; font-weight: 700; letter-spacing: -0.025em; color: oklch(18% 0.012 55);">Audit Studio</div>
</div>
<div style="padding: 0 16px 4px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: oklch(54% 0.008 55);">Аналитик</div>
""", unsafe_allow_html=True)

        analyst = st.text_input(
            "Аналитик",
            value=st.session_state.get("analyst", ""),
            placeholder="Введи своё имя",
            label_visibility="collapsed",
        )
        st.session_state["analyst"] = analyst

        st.markdown("---")

        st.page_link("app.py",                label="Анализ",    icon=":material/search:")
        st.page_link("pages/1_History.py",    label="История",   icon=":material/history:")
        st.page_link("pages/3_Dashboard.py",  label="Дашборд",   icon=":material/bar_chart:")
        st.page_link("pages/2_Settings.py",   label="Настройки", icon=":material/settings:")


def render_header(title: str, subtitle: str) -> None:
    st.markdown(f"""
<div class="hero">
    <div>
        <div class="hero-title">{title}</div>
        <div class="hero-sub">{subtitle}</div>
    </div>
</div>
""", unsafe_allow_html=True)
