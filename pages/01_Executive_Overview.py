"""
GrowthLens — Executive Overview
High-level KPIs, daily trends, device breakdown, and acquisition summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import io

import pandas as pd
import streamlit as st

from growthlens.config import DataSourceMode
from growthlens.metrics import (
    acquisition_breakdown,
    build_sessions,
    daily_trends,
    device_breakdown,
    revenue_per_purchasing_session,
    stage_conversion_rates,
    total_revenue,
)
from growthlens.visualization import (
    kpi_card_html,
    plot_daily_trends,
    plot_device_breakdown,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Executive Overview — GrowthLens", layout="wide")

st.title("📊 Executive Overview")
st.caption(
    "Session-based KPIs derived from GA4 event data. "
    "Metrics reflect the filtered date range and segments selected below."
)

# ── Guard: require session state ──────────────────────────────────────────────
if "events_df" not in st.session_state:
    st.error("No data loaded. Return to the Home page and click **Load / Refresh Data**.")
    st.stop()

raw_df: pd.DataFrame = st.session_state["events_df"]
source_mode = st.session_state.get("source_mode", DataSourceMode.DEMO)

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔎 Filters")

    # Date range
    if "event_date" in raw_df.columns:
        dates = pd.to_datetime(raw_df["event_date"]).dt.date
        min_date, max_date = dates.min(), dates.max()
        date_range = st.date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="exec_date_range",
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date, end_date = None, None

    # Device multiselect
    if "device_category" in raw_df.columns:
        all_devices = sorted(raw_df["device_category"].dropna().unique().tolist())
        sel_devices = st.multiselect("Device Category", all_devices, default=all_devices, key="exec_devices")
    else:
        all_devices, sel_devices = [], []

    # Source multiselect
    if "traffic_source" in raw_df.columns:
        all_sources = sorted(raw_df["traffic_source"].dropna().unique().tolist())
        sel_sources = st.multiselect("Traffic Source", all_sources, default=all_sources, key="exec_sources")
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


# ── Cached session build ──────────────────────────────────────────────────────
@st.cache_data(show_spinner="Building sessions…")
def _build_sessions(_df: pd.DataFrame) -> pd.DataFrame:
    return build_sessions(_df)


sessions = _build_sessions(df)

# ── Compute KPIs ──────────────────────────────────────────────────────────────
n_users = int(df["user_pseudo_id"].nunique()) if "user_pseudo_id" in df.columns else 0
n_sessions = len(sessions)
n_events = len(df)
rates = stage_conversion_rates(sessions)
rev = total_revenue(sessions)
rev_pp = revenue_per_purchasing_session(sessions)

# ── KPI cards — Row 1 ─────────────────────────────────────────────────────────
st.subheader("Key Performance Indicators")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(kpi_card_html("Unique Users", f"{n_users:,}", "pseudonymous user_pseudo_id"), unsafe_allow_html=True)
with col2:
    st.markdown(kpi_card_html("Valid Sessions", f"{n_sessions:,}", "sessions with user + session ID"), unsafe_allow_html=True)
with col3:
    st.markdown(kpi_card_html("Total Events", f"{n_events:,}", "raw event rows in filter window"), unsafe_allow_html=True)
with col4:
    funnel_entries = rates.get("sessions_view", 0)
    st.markdown(kpi_card_html("Funnel Entries", f"{funnel_entries:,}", "sessions with view_item"), unsafe_allow_html=True)

st.markdown("")

# ── KPI cards — Row 2 ─────────────────────────────────────────────────────────
col5, col6, col7, col8 = st.columns(4)

with col5:
    n_cart = rates.get("sessions_cart", 0)
    st.markdown(kpi_card_html("Sessions w/ Cart", f"{n_cart:,}", "add_to_cart reached", color="#7C3AED"), unsafe_allow_html=True)
with col6:
    n_checkout = rates.get("sessions_checkout", 0)
    st.markdown(kpi_card_html("Sessions w/ Checkout", f"{n_checkout:,}", "begin_checkout reached", color="#7C3AED"), unsafe_allow_html=True)
with col7:
    n_purchase = rates.get("sessions_purchase", 0)
    st.markdown(kpi_card_html("Purchasing Sessions", f"{n_purchase:,}", "purchase event reached", color="#059669"), unsafe_allow_html=True)
with col8:
    scr = rates.get("rate_session_to_purchase")
    scr_str = f"{scr:.2f}%" if scr is not None else "N/A"
    st.markdown(kpi_card_html("Session Conv. Rate", scr_str, "purchasing / total sessions", color="#059669"), unsafe_allow_html=True)

# ── KPI cards — Revenue Row (if available) ────────────────────────────────────
if rev is not None or rev_pp is not None:
    st.markdown("")
    col_rev1, col_rev2, _, _ = st.columns(4)
    with col_rev1:
        rev_str = f"${rev:,.2f}" if rev is not None else "N/A"
        st.markdown(kpi_card_html("Total Revenue", rev_str, "sum across purchasing sessions", color="#059669"), unsafe_allow_html=True)
    with col_rev2:
        rev_pp_str = f"${rev_pp:,.2f}" if rev_pp is not None else "N/A"
        st.markdown(kpi_card_html("Revenue / Purchase", rev_pp_str, "avg revenue per purchasing session", color="#059669"), unsafe_allow_html=True)

st.markdown("---")

# ── Daily trends ──────────────────────────────────────────────────────────────
st.subheader("Daily Traffic & Purchase Trends")

@st.cache_data(show_spinner="Computing daily trends…")
def _daily_trends(_df: pd.DataFrame) -> pd.DataFrame:
    return daily_trends(_df)

daily_df = _daily_trends(df)
if not daily_df.empty:
    st.plotly_chart(plot_daily_trends(daily_df), use_container_width=True)
else:
    st.info("No daily trend data available.")

st.markdown("---")

# ── Device breakdown ──────────────────────────────────────────────────────────
st.subheader("Device Breakdown")
dev_df = device_breakdown(sessions)
if not dev_df.empty:
    st.plotly_chart(plot_device_breakdown(dev_df), use_container_width=True)
else:
    st.info("No device data available.")

st.markdown("---")

# ── Acquisition table ─────────────────────────────────────────────────────────
st.subheader("Acquisition Summary")
acq_df = acquisition_breakdown(sessions)
if not acq_df.empty:
    display_acq = acq_df.sort_values("sessions", ascending=False).copy()
    display_acq["conversion_rate"] = display_acq["conversion_rate_pct"].apply(
        lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
    )
    st.dataframe(
        display_acq[["traffic_source", "traffic_medium", "sessions", "sessions_purchase", "conversion_rate"]].rename(
            columns={
                "traffic_source": "Source",
                "traffic_medium": "Medium",
                "sessions": "Sessions",
                "sessions_purchase": "Purchases",
                "conversion_rate": "Conv. Rate",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No acquisition data available.")

# ── Download button ───────────────────────────────────────────────────────────
st.markdown("---")
summary_data = {
    "Metric": [
        "Unique Users", "Valid Sessions", "Total Events", "Funnel Entries",
        "Sessions with Cart", "Sessions with Checkout", "Purchasing Sessions",
        "Session Conversion Rate (%)", "Total Revenue ($)", "Revenue per Purchase ($)",
    ],
    "Value": [
        n_users, n_sessions, n_events, funnel_entries,
        n_cart, n_checkout, n_purchase,
        rates.get("rate_session_to_purchase"),
        rev, rev_pp,
    ],
}
summary_df = pd.DataFrame(summary_data)
st.download_button(
    "⬇️ Download Summary CSV",
    data=summary_df.to_csv(index=False),
    file_name="growthlens_executive_summary.csv",
    mime="text/csv",
)

# ── Methodology expander ──────────────────────────────────────────────────────
with st.expander("📖 Metric Definitions & Methodology"):
    st.markdown("""
**Unique Users** — count of distinct `user_pseudo_id` values in the filtered event set.
GA4 pseudonymous IDs are not unique across devices or browsers.

**Valid Sessions** — sessions with both a valid `user_pseudo_id` and `session_id`.
Sessions missing either identifier are excluded from session-level analysis.

**Total Events** — raw event row count (after date/device/source filters).

**Funnel Entries** — sessions where at least one `view_item` event occurred.
This is the top of the purchase funnel.

**Sessions with Cart / Checkout / Purchasing Sessions** — sessions where the
`add_to_cart`, `begin_checkout`, or `purchase` event occurred at least once.
These are unordered presence flags; the funnel page applies temporal ordering.

**Session Conversion Rate** — purchasing sessions ÷ total valid sessions.
This reflects the share of all sessions (not just funnel-entering sessions) that completed a purchase.

**Total Revenue** — sum of `revenue` across purchasing sessions.
Purchasing sessions with NULL revenue are excluded (not treated as zero).

**Revenue per Purchase** — mean revenue across purchasing sessions with non-NULL revenue.

**Daily Trends** — unique users and purchase counts aggregated by `event_date`.

**Device Breakdown** — sessions and conversion rates grouped by `device_category`.

**Acquisition Summary** — sessions grouped by `traffic_source` × `traffic_medium`.
GA4 `traffic_source` fields describe **first-user acquisition**, not session-level attribution.
""")
