"""
GrowthLens — Retention Cohorts
Weekly cohort retention heatmap and summary statistics.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from growthlens.config import DataSourceMode
from growthlens.retention import assign_cohorts, build_retention_matrix, retention_summary
from growthlens.visualization import plot_retention_heatmap

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Retention Cohorts — GrowthLens", layout="wide")

st.title("🔄 Retention Cohorts")
st.caption(
    "Weekly cohort retention analysis. Cohorts are defined by first observed activity week. "
    "Immature cells (future periods not yet observable) are shown as '—'."
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
            key="ret_date_range",
        )
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date, end_date = min_date, max_date
    else:
        start_date, end_date = None, None

# ── Apply filters ─────────────────────────────────────────────────────────────
df = raw_df.copy()

if start_date and end_date and "event_date" in df.columns:
    df["_date"] = pd.to_datetime(df["event_date"]).dt.date
    df = df[(df["_date"] >= start_date) & (df["_date"] <= end_date)].drop(columns=["_date"])

if df.empty:
    st.warning("No events match the selected filters.")
    st.stop()

# ── Check for required columns ────────────────────────────────────────────────
if "event_timestamp" not in df.columns:
    st.error("Retention analysis requires `event_timestamp`. This column is absent in the current data.")
    st.stop()

if "user_pseudo_id" not in df.columns:
    st.error("Retention analysis requires `user_pseudo_id`.")
    st.stop()


# ── Cached retention matrix ───────────────────────────────────────────────────
@st.cache_data(show_spinner="Building cohort retention matrix…")
def _build_retention(_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    _df_cohorts = assign_cohorts(_df)
    _matrix = build_retention_matrix(_df_cohorts)
    _cohort_sizes = getattr(_matrix, "cohort_sizes", None)
    if _cohort_sizes is None:
        _cohort_sizes = _matrix.attrs.get("cohort_sizes", pd.Series(dtype=float))
    return _matrix, _cohort_sizes


retention_df, cohort_sizes = _build_retention(df)

if retention_df.empty:
    st.warning("Retention matrix is empty — not enough data to build cohorts.")
    st.stop()

# Ensure numeric columns are ints
retention_df.columns = [int(c) if str(c).isdigit() else c for c in retention_df.columns]

# ── Retention heatmap ─────────────────────────────────────────────────────────
st.subheader("Weekly Retention Heatmap")
st.info(
    "**'—'** cells indicate immature periods: the cohort hasn't had enough time to "
    "reach that week offset yet. These are not zero — the data simply isn't available.",
    icon="ℹ️",
)
heatmap_fig = plot_retention_heatmap(retention_df)
if heatmap_fig.data:
    st.plotly_chart(heatmap_fig, use_container_width=True)
else:
    st.info("Not enough cohort data to display heatmap.")

st.markdown("---")

# ── Cohort sizes bar chart ────────────────────────────────────────────────────
st.subheader("Cohort Sizes (Week 0 Users)")

if not cohort_sizes.empty:
    cohort_size_df = cohort_sizes.reset_index()
    cohort_size_df.columns = ["cohort_week", "users"]
    cohort_size_df["cohort_week"] = cohort_size_df["cohort_week"].astype(str).str[:10]
    cohort_size_df = cohort_size_df.sort_values("cohort_week")

    fig_sizes = px.bar(
        cohort_size_df,
        x="cohort_week",
        y="users",
        title="Users per Cohort Week",
        labels={"cohort_week": "Cohort Week", "users": "Users"},
        color_discrete_sequence=["#2563EB"],
        text="users",
    )
    fig_sizes.update_traces(textposition="outside")
    fig_sizes.update_layout(
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        showlegend=False,
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_sizes, use_container_width=True)
else:
    # Fallback: use row sums from matrix week-0 column
    if 0 in retention_df.columns:
        st.info("Cohort sizes derived from week-0 retention column.")

st.markdown("---")

# ── Average retention curve ───────────────────────────────────────────────────
st.subheader("Average Retention Curve")

avg_retention = retention_df.apply(lambda col: col.dropna().mean()).reset_index()
avg_retention.columns = ["week_offset", "avg_retention_pct"]
avg_retention = avg_retention.sort_values("week_offset")
avg_retention["n_cohorts"] = retention_df.apply(lambda col: col.dropna().count()).values

if not avg_retention.empty:
    fig_curve = go.Figure()
    fig_curve.add_trace(go.Scatter(
        x=avg_retention["week_offset"].apply(lambda w: f"Week {int(w)}"),
        y=avg_retention["avg_retention_pct"],
        mode="lines+markers",
        line=dict(color="#2563EB", width=2.5),
        marker=dict(size=8),
        hovertemplate=(
            "<b>%{x}</b><br>"
            "Avg Retention: %{y:.1f}%<br>"
            f"Based on cohorts: %{{customdata}}<extra></extra>"
        ),
        customdata=avg_retention["n_cohorts"],
    ))
    fig_curve.update_layout(
        title="Average Weekly Retention Across All Cohorts",
        xaxis=dict(title="Week Offset", gridcolor="#E2E8F0"),
        yaxis=dict(title="Avg Retention (%)", gridcolor="#E2E8F0", range=[0, 105]),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="white",
        font=dict(family="Inter, system-ui, sans-serif"),
    )
    st.plotly_chart(fig_curve, use_container_width=True)

st.markdown("---")

# ── Summary stats ─────────────────────────────────────────────────────────────
st.subheader("Retention Summary Statistics")
summary = retention_summary(retention_df)

if summary:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        w1 = summary.get("avg_w1_retention")
        st.metric("Avg Week-1 Retention", f"{w1:.1f}%" if w1 is not None else "N/A")
    with col2:
        w2 = summary.get("avg_w2_retention")
        st.metric("Avg Week-2 Retention", f"{w2:.1f}%" if w2 is not None else "N/A")
    with col3:
        w4 = summary.get("avg_w4_retention")
        st.metric("Avg Week-4 Retention", f"{w4:.1f}%" if w4 is not None else "N/A")
    with col4:
        n_w1 = summary.get("n_cohorts_w1")
        st.metric("Cohorts (Week 1)", str(n_w1) if n_w1 is not None else "N/A")

    # Best / worst cohort
    if "best_cohort_w4" in summary and "worst_cohort_w4" in summary:
        st.markdown("")
        col_best, col_worst = st.columns(2)
        with col_best:
            st.success(
                f"🏆 **Best Week-4 Cohort**: {summary['best_cohort_w4']} "
                f"({summary.get('best_cohort_w4_rate', 0):.1f}%)"
            )
        with col_worst:
            st.warning(
                f"📉 **Weakest Week-4 Cohort**: {summary['worst_cohort_w4']} "
                f"({summary.get('worst_cohort_w4_rate', 0):.1f}%)"
            )
else:
    st.info("Insufficient data to compute summary statistics.")

# ── Short-period warning ──────────────────────────────────────────────────────
st.warning(
    "⚠️ **Short Dataset Warning**: This dataset spans approximately 13 weeks (Nov 2020–Jan 2021). "
    "Most cohorts have only 1–4 observable follow-up periods. "
    "Long-term retention patterns cannot be reliably inferred from this window.",
    icon="⚠️",
)

# ── Methodology ───────────────────────────────────────────────────────────────
with st.expander("📖 Methodology & Limitations"):
    st.markdown("""
**Cohort Definition** — Each user is assigned to the **calendar week** of their
first observed event in the dataset. This is a **first-observed-activity cohort**,
not a verified account-signup or install cohort. Users whose first event occurs
outside the selected date filter may shift cohort assignments.

**Retention Measurement** — A user is counted as "retained" in week W if they
generated any event during the W-th week after their cohort week.
Week 0 = 100% by definition (all cohort members are active in their entry week).

**Immature Cells** — A cell (cohort C, week W) is **immature** when the expected
end of week W falls after the last event in the dataset. These cells are displayed
as '—' (not zero). Treating immature cells as zero would artificially deflate retention.

**Dataset Limitation** — The GA4 obfuscated sample covers ≈13 weeks.
- Recent cohorts have few or no observable follow-up weeks.
- Week-4+ retention is available only for the earliest cohorts.
- Do not extrapolate these patterns to annual retention curves.

**Average Retention Curve** — Computed as the mean across all cohorts with observable data
at each week offset. The number of contributing cohorts decreases at higher offsets.
""")
