"""
GrowthLens — Acquisition Insights
Channel and device performance analysis with attribution caveats.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import io

import pandas as pd
import streamlit as st

from growthlens.acquisition import acquisition_findings, acquisition_performance, device_performance
from growthlens.config import DataSourceMode
from growthlens.metrics import build_sessions, session_conversion_rate
from growthlens.visualization import plot_acquisition_matrix, plot_device_breakdown

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Acquisition Insights — GrowthLens", layout="wide")

st.title("📡 Acquisition Insights")
st.caption(
    "Channel and device performance analysis based on GA4 session data."
)

# ── Attribution disclaimer ─────────────────────────────────────────────────────
st.info(
    "ℹ️ **Attribution Notice**: GA4 `traffic_source` fields describe **first-user acquisition** "
    "(the channel that originally acquired the user), NOT session-level attribution. "
    "A user acquired via organic search may have their current session classified as 'direct'. "
    "No ROAS or CAC data is available in this dataset.",
    icon="ℹ️",
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
            key="acq_date_range",
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date, end_date = None, None

    if "device_category" in raw_df.columns:
        all_devices = sorted(raw_df["device_category"].dropna().unique().tolist())
        sel_devices = st.multiselect("Device Category", all_devices, default=all_devices, key="acq_devices")
    else:
        all_devices, sel_devices = [], []

# ── Apply filters ─────────────────────────────────────────────────────────────
df = raw_df.copy()

if start_date and end_date and "event_date" in df.columns:
    df["_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = df[(df["_date"] >= start_date) & (df["_date"] <= end_date)].drop(columns=["_date"])

if sel_devices and "device_category" in df.columns:
    df = df[df["device_category"].isin(sel_devices)]

if df.empty:
    st.warning("No events match the selected filters.")
    st.stop()


# ── Cached computations ───────────────────────────────────────────────────────
@st.cache_data(show_spinner="Building sessions…")
def _build_sessions(_df: pd.DataFrame) -> pd.DataFrame:
    return build_sessions(_df)


@st.cache_data(show_spinner="Computing acquisition performance…")
def _acq_perf(_sessions: pd.DataFrame) -> pd.DataFrame:
    return acquisition_performance(_sessions)


@st.cache_data(show_spinner="Computing device performance…")
def _dev_perf(_sessions: pd.DataFrame) -> pd.DataFrame:
    return device_performance(_sessions)


sessions = _build_sessions(df)
acq_df = _acq_perf(sessions)
dev_df = _dev_perf(sessions)
overall_conv = session_conversion_rate(sessions)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_source, tab_device, tab_matrix = st.tabs(["📊 Source Analysis", "📱 Device Analysis", "🫧 Channel Matrix"])

# ── Tab 1: Source Analysis ────────────────────────────────────────────────────
with tab_source:
    st.subheader("Acquisition Performance by Source × Medium")
    if not acq_df.empty:
        # Conditional coloring for conversion rate
        display_acq = acq_df.copy()
        avg_conv = display_acq["conversion_rate_pct"].mean()

        def _conv_color(val: float) -> str:
            if pd.isna(val):
                return ""
            if val >= avg_conv * 1.2:
                return "background-color: #D1FAE5"
            elif val < avg_conv * 0.7:
                return "background-color: #FEE2E2"
            return "background-color: #FEF3C7"

        display_cols = [c for c in [
            "traffic_source", "traffic_medium", "sessions", "users",
            "sessions_view", "sessions_purchase", "conversion_rate_pct",
            "view_rate_pct", "cart_rate_pct", "low_sample",
        ] if c in display_acq.columns]

        rename_map = {
            "traffic_source": "Source",
            "traffic_medium": "Medium",
            "sessions": "Sessions",
            "users": "Users",
            "sessions_view": "View Sessions",
            "sessions_purchase": "Purchases",
            "conversion_rate_pct": "Conv. Rate (%)",
            "view_rate_pct": "View Rate (%)",
            "cart_rate_pct": "Cart Rate (%)",
            "low_sample": "Low Sample?",
        }

        styler = display_acq[display_cols].rename(columns=rename_map).style
        if hasattr(styler, "map"):
            styled = styler.map(_conv_color, subset=["Conv. Rate (%)"])
        else:
            styled = styler.applymap(_conv_color, subset=["Conv. Rate (%)"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("No acquisition source data available.")

    # Findings
    if not acq_df.empty and overall_conv is not None:
        st.subheader("🔍 Acquisition Findings")
        findings = acquisition_findings(acq_df, overall_rate=overall_conv)
        if findings:
            for f in findings:
                severity = f.get("severity", "medium")
                css_class = "finding-high" if severity == "high" else "finding-medium"
                icon = "🔴" if severity == "high" else "🟡"
                st.markdown(
                    f'<div class="{css_class}"><strong>{icon} {severity.title()}</strong><br>{f["message"]}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("No significant acquisition patterns detected.")

# ── Tab 2: Device Analysis ────────────────────────────────────────────────────
with tab_device:
    st.subheader("Device Performance")
    if not dev_df.empty:
        st.plotly_chart(plot_device_breakdown(dev_df), use_container_width=True)

        st.markdown("#### Device Metrics Table")
        display_dev = dev_df.copy()
        dev_display_cols = [c for c in [
            "device_category", "sessions", "users", "sessions_view",
            "sessions_purchase", "conversion_rate_pct", "low_sample",
        ] if c in display_dev.columns]
        dev_rename = {
            "device_category": "Device",
            "sessions": "Sessions",
            "users": "Users",
            "sessions_view": "View Sessions",
            "sessions_purchase": "Purchases",
            "conversion_rate_pct": "Conv. Rate (%)",
            "low_sample": "Low Sample?",
        }
        st.dataframe(
            display_dev[dev_display_cols].rename(columns=dev_rename),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No device data available.")

# ── Tab 3: Channel Matrix ─────────────────────────────────────────────────────
with tab_matrix:
    st.subheader("Volume vs Conversion Bubble Chart")
    if not acq_df.empty:
        fig_matrix = plot_acquisition_matrix(acq_df)
        if fig_matrix.data:
            st.plotly_chart(fig_matrix, use_container_width=True)
            st.caption(
                "Each bubble represents a source/medium combination. "
                "Bubble size = session volume. "
                "Segments with fewer than the minimum sample size are excluded."
            )
        else:
            st.info("Not enough qualifying segments to display the matrix chart.")
    else:
        st.info("No acquisition data available for matrix chart.")

# ── Methodology ───────────────────────────────────────────────────────────────
with st.expander("📖 Attribution Methodology & Limitations"):
    st.markdown("""
**First-User Attribution** — GA4's `traffic_source`, `traffic_medium`, and `traffic_campaign`
fields capture the channel that **first acquired** the user, not the channel driving the current session.
A returning user originally acquired via paid search who visits directly will still show `traffic_source = google`.

**Session-Level vs. User-Level** — Conversion rates here are computed at the **session level**
(purchasing sessions ÷ total sessions). This differs from user-level conversion (converting users ÷ total users).

**No ROAS / CAC** — Advertising spend data is not available in the GA4 obfuscated sample dataset.
Return on ad spend (ROAS) and customer acquisition cost (CAC) cannot be computed.

**Low-Sample Warning** — Channels with fewer than {MIN_SEGMENT_SIZE} sessions are flagged.
Conversion rates for small segments are statistically unreliable.

**Channel Matrix** — Excludes low-sample segments to prevent over-interpretation of noisy data.
Use the Source Analysis table for a complete view including low-sample channels.
""".format(MIN_SEGMENT_SIZE=30))
