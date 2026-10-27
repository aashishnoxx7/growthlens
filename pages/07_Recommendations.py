"""
GrowthLens — Business Recommendations
Actionable, transparent, rule-based recommendations derived from observed data.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import streamlit as st

from growthlens.acquisition import acquisition_performance, device_performance
from growthlens.config import DataSourceMode
from growthlens.data_quality import run_all_quality_checks
from growthlens.funnel import compute_ordered_funnel, funnel_findings
from growthlens.metrics import build_sessions, session_conversion_rate
from growthlens.recommendations import generate_recommendations
from growthlens.retention import assign_cohorts, build_retention_matrix, retention_summary

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Recommendations — GrowthLens", layout="wide")

# ── Verify session state ──────────────────────────────────────────────────────
if "events_df" not in st.session_state:
    st.error("No data loaded. Please return to the main page to load data first.")
    st.stop()

df_raw: pd.DataFrame = st.session_state["events_df"]

st.title("🎯 Actionable Business Recommendations")
st.caption(
    "Defensible, rule-based recommendations generated directly from observed funnel bottlenecks, "
    "device discrepancies, acquisition conversion rates, and data-integrity flags."
)

# ── Notice on Causality ───────────────────────────────────────────────────────
st.markdown(
    """
<div style="
    background: #F8FAFC;
    border: 1px solid #CBD5E1;
    border-left: 5px solid #2563EB;
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 24px;
">
  <div style="font-size: 14px; font-weight: 600; color: #1E293B;">
    ⚠️ Methodological Standard: Association vs. Causation
  </div>
  <div style="font-size: 13px; color: #475569; margin-top: 4px;">
    All recommendations below are derived from <strong>observed empirical patterns</strong> in historical records.
    Drop-offs and conversion variances indicate where to investigate, not conclusive proof of a specific UX bug or marketing failure.
    Each action is structured as a testable hypothesis with a defined validation protocol.
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Sidebar Filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filters")
    min_date = pd.to_datetime(df_raw["event_date"]).min().date()
    max_date = pd.to_datetime(df_raw["event_date"]).max().date()

    date_range = st.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    devices = sorted(df_raw["device_category"].dropna().unique().tolist())
    selected_devices = st.multiselect("Device Category", devices, default=devices)

# Apply filters
df = df_raw.copy()
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    s_date, e_date = date_range
    df = df[(pd.to_datetime(df["event_date"]).dt.date >= s_date) & 
            (pd.to_datetime(df["event_date"]).dt.date <= e_date)]

if selected_devices and "device_category" in df.columns:
    df = df[df["device_category"].isin(selected_devices)]

if df.empty:
    st.warning("No records match the selected filters.")
    st.stop()


# ── Calculate recommendations across modules ──────────────────────────────────
@st.cache_data(show_spinner=True)
def _compute_all_recommendations(data: pd.DataFrame) -> list[dict]:
    # 1. Sessions & overall conversion
    sessions = build_sessions(data)
    overall_conv = session_conversion_rate(sessions)

    # 2. Funnel & funnel findings
    funnel_df = compute_ordered_funnel(data)
    f_findings = funnel_findings(funnel_df, overall_conversion=overall_conv)

    # 3. Acquisition & device performance
    acq_df = acquisition_performance(sessions)
    dev_df = device_performance(sessions)

    # 4. Retention summary
    df_cohorts = assign_cohorts(data)
    ret_matrix = build_retention_matrix(df_cohorts)
    ret_sum = retention_summary(ret_matrix)

    # 5. Data quality checks
    q_checks = run_all_quality_checks(data)

    # 6. Generate recommendations
    recs = generate_recommendations(
        funnel_df=funnel_df,
        funnel_findings=f_findings,
        acquisition_df=acq_df,
        device_df=dev_df,
        retention_summary=ret_sum,
        quality_checks=q_checks,
        overall_conversion=overall_conv,
    )
    return recs


recommendations = _compute_all_recommendations(df)

# ── Summary Metrics ───────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
total_recs = len(recommendations)
high_prio = sum(1 for r in recommendations if r["priority"] == "High")
med_prio = sum(1 for r in recommendations if r["priority"] == "Medium")
categories_covered = len({r["category"] for r in recommendations})

c1.metric("Total Recommendations", f"{total_recs}")
c2.metric("High Priority (P1)", f"{high_prio}")
c3.metric("Medium Priority (P2)", f"{med_prio}")
c4.metric("Categories Identified", f"{categories_covered}")

st.markdown("---")

if not recommendations:
    st.info(
        "ℹ️ No anomalous patterns or threshold violations were detected for the selected filters. "
        "Either the sample size is below required minimums (30 sessions per segment) or conversion rates are balanced."
    )
    st.stop()

# ── Category / Priority Filter ────────────────────────────────────────────────
col_f1, col_f2 = st.columns(2)
with col_f1:
    cat_options = ["All Categories"] + sorted(list({r["category"] for r in recommendations}))
    chosen_cat = st.selectbox("Filter by Category", cat_options)
with col_f2:
    prio_options = ["All Priorities", "High", "Medium", "Low"]
    chosen_prio = st.selectbox("Filter by Priority", prio_options)

filtered_recs = recommendations
if chosen_cat != "All Categories":
    filtered_recs = [r for r in filtered_recs if r["category"] == chosen_cat]
if chosen_prio != "All Priorities":
    filtered_recs = [r for r in filtered_recs if r["priority"] == chosen_prio]

st.markdown(f"### Prioritized Opportunities ({len(filtered_recs)} Actions)")

# ── Render Recommendation Cards ───────────────────────────────────────────────
for rec in filtered_recs:
    prio = rec["priority"]
    if prio == "High":
        prio_badge = '<span style="background:#FEE2E2;color:#991B1B;padding:4px 10px;border-radius:4px;font-weight:700;font-size:12px;">P1 — HIGH PRIORITY</span>'
        border_color = "#EF4444"
    elif prio == "Medium":
        prio_badge = '<span style="background:#FEF3C7;color:#92400E;padding:4px 10px;border-radius:4px;font-weight:700;font-size:12px;">P2 — MEDIUM PRIORITY</span>'
        border_color = "#F59E0B"
    else:
        prio_badge = '<span style="background:#DBEAFE;color:#1E40AF;padding:4px 10px;border-radius:4px;font-weight:700;font-size:12px;">P3 — LOW PRIORITY</span>'
        border_color = "#3B82F6"

    cat_badge = f'<span style="background:#F1F5F9;color:#334155;padding:4px 10px;border-radius:4px;font-weight:600;font-size:12px;margin-left:8px;">{rec["category"]}</span>'

    st.markdown(
        f"""
<div style="
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-left: 6px solid {border_color};
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
">
  <div style="margin-bottom: 12px;">
    {prio_badge} {cat_badge}
    <span style="font-size: 12px; color: #64748B; float: right;">Scope: <strong>{rec['affected_segment']}</strong></span>
  </div>
  <div style="font-size: 18px; font-weight: 700; color: #1E293B; margin-bottom: 8px;">
    {rec['problem']}
  </div>
  <div style="font-size: 14px; color: #334155; margin-bottom: 12px;">
    <strong>Observed Evidence:</strong> {rec['evidence']}
  </div>
  <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px;">
    <div style="font-size: 13px; font-weight: 700; color: #1E293B; margin-bottom: 4px;">🛠️ Recommended Action:</div>
    <div style="font-size: 13px; color: #334155;">{rec['recommended_action']}</div>
  </div>
  <div style="font-size: 13px; color: #475569; margin-bottom: 6px;">
    <strong>💡 Hypothesis / Expected Direction:</strong> {rec['expected_direction']}
  </div>
  <div style="font-size: 13px; color: #475569; margin-bottom: 6px;">
    <strong>🧪 How to Validate:</strong> {rec['how_to_test']}
  </div>
  <div style="font-size: 12px; color: #64748B; font-style: italic; margin-top: 8px;">
    <strong>⚠️ Analytical Limitation:</strong> {rec['limitations']}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ── Download Recommendations ──────────────────────────────────────────────────
st.subheader("Export Action Plan")

recs_export_df = pd.DataFrame([
    {
        "Priority": r["priority"],
        "Category": r["category"],
        "Affected Segment": r["affected_segment"],
        "Problem": r["problem"],
        "Evidence": r["evidence"],
        "Recommended Action": r["recommended_action"],
        "Expected Direction": r["expected_direction"],
        "Validation Plan": r["how_to_test"],
        "Limitations": r["limitations"],
    }
    for r in recommendations
])

col_d1, _ = st.columns([1, 4])
with col_d1:
    st.download_button(
        "⬇️ Download Action Plan (CSV)",
        data=recs_export_df.to_csv(index=False).encode("utf-8"),
        file_name="growthlens_recommendations_action_plan.csv",
        mime="text/csv",
        use_container_width=True,
    )
