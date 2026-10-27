"""
GrowthLens — Conversion Funnel
Session-based, temporally-ordered conversion funnel analysis with segmentation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import io

import pandas as pd
import streamlit as st

from growthlens.config import DataSourceMode, MIN_SEGMENT_SIZE
from growthlens.funnel import compute_funnel_by_segment, compute_ordered_funnel, funnel_findings
from growthlens.metrics import build_sessions, session_conversion_rate
from growthlens.visualization import plot_funnel, plot_funnel_bars

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Conversion Funnel — GrowthLens", layout="wide")

st.title("🔻 Conversion Funnel")
st.caption(
    "Session-based, temporally-ordered funnel. A session progresses to stage N only if "
    "stage N-1 occurred first (by event_timestamp). Each stage uses the first valid occurrence."
)

# ── Guard ─────────────────────────────────────────────────────────────────────
if "events_df" not in st.session_state:
    st.error("No data loaded. Return to the Home page and click **Load / Refresh Data**.")
    st.stop()

raw_df: pd.DataFrame = st.session_state["events_df"]
source_mode = st.session_state.get("source_mode", DataSourceMode.DEMO)

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔎 Filters")

    if "event_date" in raw_df.columns:
        dates = pd.to_datetime(raw_df["event_date"]).dt.date
        min_date, max_date = dates.min(), dates.max()
        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="funnel_date_range",
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date, end_date = None, None

    segment_col = st.selectbox(
        "Segment By",
        options=["device_category", "traffic_source"],
        key="funnel_segment",
    )

    if "device_category" in raw_df.columns:
        all_devices = sorted(raw_df["device_category"].dropna().unique().tolist())
        sel_devices = st.multiselect("Device Category", all_devices, default=all_devices, key="funnel_devices")
    else:
        all_devices, sel_devices = [], []

    if "traffic_source" in raw_df.columns:
        all_sources = sorted(raw_df["traffic_source"].dropna().unique().tolist())
        sel_sources = st.multiselect("Traffic Source", all_sources, default=all_sources, key="funnel_sources")
    else:
        all_sources, sel_sources = [], []

# ── Apply filters ─────────────────────────────────────────────────────────────
df = raw_df.copy()

if start_date and end_date and "event_date" in df.columns:
    df["_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = df[(df["_date"] >= start_date) & (df["_date"] <= end_date)].drop(columns=["_date"])

if sel_devices and "device_category" in df.columns:
    df = df[df["device_category"].isin(sel_devices)]

if sel_sources and "traffic_source" in df.columns:
    df = df[df["traffic_source"].isin(sel_sources)]

if df.empty:
    st.warning("No events match the selected filters.")
    st.stop()


# ── Cached computations ───────────────────────────────────────────────────────
@st.cache_data(show_spinner="Computing ordered funnel…")
def _compute_funnel(_df: pd.DataFrame) -> pd.DataFrame:
    return compute_ordered_funnel(_df)


@st.cache_data(show_spinner="Computing segmented funnel…")
def _compute_segmented(_df: pd.DataFrame, segment_col: str) -> pd.DataFrame:
    return compute_funnel_by_segment(_df, segment_col=segment_col)


@st.cache_data(show_spinner="Building sessions…")
def _build_sessions(_df: pd.DataFrame) -> pd.DataFrame:
    return build_sessions(_df)


funnel_df = _compute_funnel(df)
seg_df = _compute_segmented(df, segment_col=segment_col)
sessions = _build_sessions(df)
overall_conv = session_conversion_rate(sessions)

# ── Funnel charts in tabs ─────────────────────────────────────────────────────
st.subheader("Funnel Visualization")
tab_funnel, tab_bars = st.tabs(["📉 Funnel Chart", "📊 Bar Chart"])

with tab_funnel:
    if not funnel_df.empty and funnel_df["sessions"].iloc[0] > 0:
        st.plotly_chart(plot_funnel(funnel_df), use_container_width=True)
    else:
        st.info("Insufficient funnel data in the selected range.")

with tab_bars:
    if not funnel_df.empty and funnel_df["sessions"].iloc[0] > 0:
        st.plotly_chart(plot_funnel_bars(funnel_df), use_container_width=True)
    else:
        st.info("Insufficient funnel data in the selected range.")

st.markdown("---")

# ── Funnel table ──────────────────────────────────────────────────────────────
st.subheader("Funnel Metrics Table")
if not funnel_df.empty:
    display_cols = ["label", "sessions", "pct_of_first_stage", "pct_of_prev_stage", "dropoff_abs", "dropoff_pct"]
    available_cols = [c for c in display_cols if c in funnel_df.columns]
    rename_map = {
        "label": "Stage",
        "sessions": "Sessions",
        "pct_of_first_stage": "% of First Stage",
        "pct_of_prev_stage": "% of Previous Stage",
        "dropoff_abs": "Drop-off (#)",
        "dropoff_pct": "Drop-off (%)",
    }
    table = funnel_df[available_cols].rename(columns=rename_map)
    st.dataframe(table, use_container_width=True, hide_index=True)

st.markdown("---")

# ── Segment funnel comparison ─────────────────────────────────────────────────
st.subheader(f"Conversion Rate by {segment_col.replace('_', ' ').title()}")

if not seg_df.empty:
    from growthlens.config import FUNNEL_STAGES

    purchase_stage = FUNNEL_STAGES[-1]
    first_stage = FUNNEL_STAGES[0]

    seg_purchase = seg_df[seg_df["stage"] == purchase_stage][["segment", "sessions", "low_sample"]].copy()
    seg_entry = seg_df[seg_df["stage"] == first_stage][["segment", "sessions"]].rename(columns={"sessions": "entry"})
    seg_merged = seg_purchase.merge(seg_entry, on="segment", how="left")
    seg_merged["conv_rate_pct"] = (seg_merged["sessions"] / seg_merged["entry"] * 100).round(2)

    low_sample_segs = seg_merged[seg_merged["low_sample"]]["segment"].tolist()
    if low_sample_segs:
        st.warning(
            f"⚠️ Segments with fewer than {MIN_SEGMENT_SIZE} sessions (results may be unreliable): "
            + ", ".join(str(s) for s in low_sample_segs)
        )

    seg_chart = seg_merged[~seg_merged["low_sample"]].sort_values("conv_rate_pct", ascending=False)
    if not seg_chart.empty:
        import plotly.express as px

        fig = px.bar(
            seg_chart,
            x="segment",
            y="conv_rate_pct",
            color="segment",
            text=seg_chart["conv_rate_pct"].apply(lambda x: f"{x:.2f}%"),
            title=f"Purchase Conversion Rate by {segment_col.replace('_', ' ').title()}",
            labels={"segment": segment_col.replace("_", " ").title(), "conv_rate_pct": "Conversion Rate (%)"},
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, plot_bgcolor="#F8FAFC", paper_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No segments with ≥ {MIN_SEGMENT_SIZE} sessions available for comparison.")
else:
    st.info("No segment data available.")

st.markdown("---")

# ── Findings ──────────────────────────────────────────────────────────────────
st.subheader("🔍 Funnel Findings")
findings = funnel_findings(
    funnel_df,
    segmented_df=seg_df if not seg_df.empty else None,
    overall_conversion=overall_conv,
)

if findings:
    for finding in findings:
        severity = finding.get("severity", "medium")
        css_class = "finding-high" if severity == "high" else "finding-medium"
        icon = "🔴" if severity == "high" else "🟡"
        st.markdown(
            f'<div class="{css_class}">'
            f"<strong>{icon} {severity.title()} Priority</strong><br>"
            f"{finding['message']}"
            f"</div>",
            unsafe_allow_html=True,
        )
else:
    st.info("No significant funnel patterns detected in the current filter window.")

# ── Methodology ───────────────────────────────────────────────────────────────
with st.expander("📖 Methodology"):
    st.markdown(f"""
**Ordered Temporal Funnel** — A session is counted at stage N only when:
1. The session contains at least one event of type N, AND
2. The first occurrence of stage N happens **after** the first occurrence of stage N-1.

This prevents inflated stage counts from out-of-order event firing.

**First-Occurrence Rule** — Only the earliest timestamp for each stage within a session is used.
Repeated events (e.g., multiple `view_item` events) do not increase the session count.

**Session-Level Counting** — All funnel metrics count distinct sessions, not events or users.
A single user may appear in multiple sessions; each session is evaluated independently.

**Minimum Segment Size** — Segments with fewer than **{MIN_SEGMENT_SIZE} sessions** are flagged
as potentially unreliable and excluded from comparative visualizations.

**Dataset Limitation** — This dataset covers a short window (~13 weeks).
Interpret conversion rates as a snapshot, not a long-term baseline.
""")
