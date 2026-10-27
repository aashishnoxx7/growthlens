"""
GrowthLens — Main App Entry Point
From User Behavior to Business Decisions

Navigation is handled by Streamlit's multi-page app system.
This file configures the app, manages session state, and provides
a global data-loading UI so all pages share a consistent dataset.
"""

import logging
import sys
from pathlib import Path

import streamlit as st

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growthlens.config import DataSourceMode, bq_available
from growthlens.data_loader import list_local_data_files, load_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("growthlens.app")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GrowthLens",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/your-org/growthlens",
        "About": "GrowthLens — Product Analytics Intelligence Platform",
    },
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #1E293B !important;
}
[data-testid="stSidebar"] * {
    color: #E2E8F0 !important;
}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {
    color: #CBD5E1 !important;
    font-size: 12px !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* Main headers */
h1 { color: #1E293B !important; font-weight: 700 !important; }
h2 { color: #1E293B !important; font-weight: 600 !important; }
h3 { color: #334155 !important; font-weight: 600 !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #fff;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,.05);
}

/* Dividers */
hr { border: none; border-top: 1px solid #E2E8F0; margin: 24px 0; }

/* Demo banner */
.demo-banner {
    background: linear-gradient(135deg, #FEF3C7, #FDE68A);
    border: 1px solid #F59E0B;
    border-radius: 8px;
    padding: 12px 20px;
    font-weight: 600;
    color: #92400E;
    text-align: center;
    font-size: 13px;
    letter-spacing: 0.03em;
}

/* Status badges */
.badge-demo { background:#FEF3C7; color:#92400E; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; }
.badge-bq   { background:#D1FAE5; color:#065F46; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; }
.badge-local{ background:#EDE9FE; color:#4C1D95; border-radius:4px; padding:2px 8px; font-size:11px; font-weight:600; }

/* Findings */
.finding-high   { background:#FEF2F2; border-left:4px solid #DC2626; padding:12px 16px; border-radius:4px; margin:8px 0; }
.finding-medium { background:#FFFBEB; border-left:4px solid #D97706; padding:12px 16px; border-radius:4px; margin:8px 0; }
.finding-low    { background:#EFF6FF; border-left:4px solid #2563EB; padding:12px 16px; border-radius:4px; margin:8px 0; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar: Data source ──────────────────────────────────────────────────────
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("""
        <div style="padding:20px 0 16px;">
          <div style="font-size:22px;font-weight:700;color:#F1F5F9;">🔍 GrowthLens</div>
          <div style="font-size:11px;color:#94A3B8;margin-top:2px;">
            From User Behavior to Business Decisions
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()
        st.markdown('<div style="font-size:11px;color:#94A3B8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;">Data Source</div>', unsafe_allow_html=True)

        modes = []
        labels = []
        local_files = [f for f in list_local_data_files() if "demo" not in f.name.lower()]
        if not local_files:
            local_files = list_local_data_files()
            
        if local_files:
            modes.append(DataSourceMode.LOCAL)
            labels.append("📁 Production Data (Local)")
        if bq_available():
            modes.append(DataSourceMode.BIGQUERY)
            labels.append("☁️ Google Cloud BigQuery")
        if not modes:
            modes.append(DataSourceMode.DEMO)
            labels.append("📁 Sample Data")

        selected_label = st.radio(
            "Source",
            labels,
            index=0,
            key="source_mode_label",
            label_visibility="collapsed",
        )
        mode = modes[labels.index(selected_label)]

        local_path = None
        if mode == DataSourceMode.LOCAL:
            file_names = [f.name for f in local_files]
            default_idx = file_names.index("real_retail_events.parquet") if "real_retail_events.parquet" in file_names else 0
            chosen = st.selectbox("Choose dataset", file_names, index=default_idx, key="local_file_choice")
            local_path = next(f for f in local_files if f.name == chosen)

        load_btn = st.button("⟳ Load / Refresh Data", use_container_width=True, type="primary")

        if load_btn or "events_df" not in st.session_state:
            with st.spinner("Loading data…"):
                try:
                    df, src_label, warnings = load_data(
                        mode=mode,
                        local_path=local_path,
                    )
                    st.session_state["events_df"] = df
                    st.session_state["source_label"] = src_label
                    st.session_state["source_mode"] = mode
                    st.session_state["source_warnings"] = warnings
                    logger.info("Data loaded: %d events from %s", len(df), src_label)
                except Exception as exc:
                    st.error(f"Failed to load data: {exc}")
                    logger.exception("Data load error")

        # ── Source status ─────────────────────────────────────────────────────
        if "source_label" in st.session_state:
            st.divider()
            src = st.session_state["source_label"]
            mode_cur = st.session_state.get("source_mode", DataSourceMode.DEMO)
            badge = (
                "badge-bq" if mode_cur == DataSourceMode.BIGQUERY else
                "badge-local" if mode_cur == DataSourceMode.LOCAL else
                "badge-demo"
            )
            icon = "☁️" if mode_cur == DataSourceMode.BIGQUERY else "📁" if mode_cur == DataSourceMode.LOCAL else "🧪"
            st.markdown(
                f'<div class="{badge}" style="margin-bottom:8px">{icon} {src[:45]}</div>',
                unsafe_allow_html=True,
            )
            df = st.session_state["events_df"]
            st.markdown(f"<div style='font-size:12px;color:#94A3B8'>{len(df):,} events loaded</div>", unsafe_allow_html=True)

            warnings = st.session_state.get("source_warnings", [])
            if warnings:
                with st.expander(f"⚠️ {len(warnings)} schema warning(s)"):
                    for w in warnings:
                        st.caption(w)

        st.divider()
        st.caption("GA4 Obfuscated Sample • Nov 2020–Jan 2021")
        st.caption("Historical data — not current Google performance")


render_sidebar()

# ── Home page ─────────────────────────────────────────────────────────────────
if "events_df" not in st.session_state:
    st.title("🔍 GrowthLens")
    st.info("Select a data source from the sidebar and click **Load / Refresh Data** to begin.")
    st.stop()

st.title("🔍 GrowthLens")
st.subheader("From User Behavior to Business Decisions")
st.markdown(
    "Welcome to **GrowthLens** — a product analytics intelligence platform. "
    "Use the sidebar to navigate to any analysis page."
)

col1, col2, col3 = st.columns(3)
df = st.session_state["events_df"]

with col1:
    st.metric("Total Events", f"{len(df):,}")
with col2:
    st.metric("Unique Users", f"{df['user_pseudo_id'].nunique():,}")
with col3:
    if "session_key" in df.columns:
        st.metric("Valid Sessions", f"{df['session_key'].nunique():,}")

st.markdown("---")
st.markdown("""
### Navigate the Analysis

| Page | What it answers |
|---|---|
| **01 Executive Overview** | High-level KPIs, trends, and where to investigate first |
| **02 Conversion Funnel** | Where sessions drop off in the purchase journey |
| **03 Retention Cohorts** | Which user cohorts return and how often |
| **04 Acquisition Insights** | Which channels and devices drive quality traffic |
| **05 Experiment Lab** | Simulate A/B tests with real statistical calculations |
| **06 Data Quality** | Whether the data is trustworthy for analysis |
| **07 Recommendations** | Prioritized, evidence-based actions |
""")
