"""
GrowthLens — Data Quality and Trust
Automated data-quality checks, severity assessment, and metric trustworthiness.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import streamlit as st

from growthlens.config import DataSourceMode
from growthlens.data_quality import quality_summary, run_all_quality_checks

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Data Quality — GrowthLens", layout="wide")

# ── Verify session state ──────────────────────────────────────────────────────
if "events_df" not in st.session_state:
    st.error("No data loaded. Please go to the main page to load data first.")
    st.stop()

df_raw: pd.DataFrame = st.session_state["events_df"]

st.title("🛡️ Data Quality & Trust")
st.caption(
    "Automated data integrity checks evaluate whether underlying GA4 records "
    "are reliable for conversion, revenue, and retention analysis."
)

# ── Sidebar: Filters ──────────────────────────────────────────────────────────
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


# ── Run checks ────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=True)
def _run_checks(data: pd.DataFrame) -> tuple[list[dict], dict]:
    results = run_all_quality_checks(data)
    summary = quality_summary(results)
    return results, summary


check_results, summary = _run_checks(df)

# ── Overall Quality Badge & Score ─────────────────────────────────────────────
status = summary["overall_status"]
if status == "pass":
    status_color = "#059669"
    status_bg = "#ECFDF5"
    status_border = "#10B981"
    status_text = "PASSED — DATA IS SUITABLE FOR ANALYSIS"
    status_desc = "All critical integrity checks passed. Analysis results can be interpreted with high confidence."
elif status == "warn":
    status_color = "#D97706"
    status_bg = "#FFFBEB"
    status_border = "#F59E0B"
    status_text = "WARNINGS DETECTED — REVIEW IMPACTED METRICS"
    status_desc = "Non-critical issues or minor sample anomalies detected. Proceed with segmentation caveats."
else:
    status_color = "#DC2626"
    status_bg = "#FEF2F2"
    status_border = "#EF4444"
    status_text = "FAILURES DETECTED — CRITICAL DATA INTEGRITY ISSUES"
    status_desc = "One or more critical checks failed. Associated KPIs (e.g. revenue, attribution) should be withheld or qualified."

st.markdown(
    f"""
<div style="
    background: {status_bg};
    border: 1px solid {status_border};
    border-left: 6px solid {status_color};
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 24px;
">
  <div style="font-size: 16px; font-weight: 700; color: {status_color};">
    {status_text}
  </div>
  <div style="font-size: 13px; color: #475569; margin-top: 4px;">
    {status_desc}
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Summary metrics ───────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Checks Evaluated", f"{summary['total_checks']}")
c2.metric("Passed Checks", f"{summary['passes']}", delta=None)
c3.metric("Warnings", f"{summary['warnings']}", delta=f"{summary['warnings']} flagged" if summary['warnings'] else None, delta_color="inverse")
c4.metric("Errors / Critical", f"{summary['errors']}", delta=f"{summary['errors']} failed" if summary['errors'] else None, delta_color="inverse")

st.markdown("---")

# ── Checks Table ──────────────────────────────────────────────────────────────
st.subheader("Data Quality Check Matrix")

table_data = []
for c in check_results:
    table_data.append({
        "Check Name": c["check_name"],
        "Severity": c["severity"].upper(),
        "Status": c["status"].upper(),
        "Affected Rows": f"{c['affected_rows']:,}",
        "% Affected": f"{c['pct_affected']:.2f}%",
        "Diagnostic Message": c["message"],
    })

report_df = pd.DataFrame(table_data)

# Styled display
def _highlight_status(row):
    status_val = row["Status"]
    if status_val == "FAIL":
        return ["background-color: #FEF2F2; color: #991B1B"] * len(row)
    elif status_val == "WARN":
        return ["background-color: #FFFBEB; color: #92400E"] * len(row)
    return [""] * len(row)

st.dataframe(report_df, use_container_width=True, hide_index=True)

# ── Detailed Diagnostics & Remediation ────────────────────────────────────────
st.subheader("Diagnostic Breakdown & Recommended Remediation")

for c in check_results:
    sev_icon = "🔴" if c["severity"] == "error" else "🟡" if c["severity"] == "warning" else "🔵"
    status_badge = "✅ PASS" if c["status"] == "pass" else "⚠️ WARN" if c["status"] == "warn" else "❌ FAIL"
    
    with st.expander(f"{sev_icon} **{c['check_name']}** — {status_badge} ({c['affected_rows']:,} rows, {c['pct_affected']:.2f}%)"):
        st.write(f"**Description / Findings:** {c['message']}")
        if c.get("remediation"):
            st.info(f"**Remediation Action:** {c['remediation']}")
        st.caption(f"Severity: {c['severity'].upper()} | Evaluation Scope: {c['total_rows']:,} events")

st.markdown("---")

# ── Specific Revenue Integrity Deep Dive ──────────────────────────────────────
st.subheader("Ecommerce & Revenue Integrity Inspection")

col_r1, col_r2 = st.columns(2)

with col_r1:
    st.markdown("##### Purchase Events & Transaction Completeness")
    purchases = df[df["event_name"] == "purchase"]
    total_purchases = len(purchases)
    
    if total_purchases == 0:
        st.write("No purchase events found in the filtered window.")
    else:
        null_rev = purchases["revenue"].isna().sum() if "revenue" in purchases.columns else 0
        missing_tid = purchases["transaction_id"].isna().sum() if "transaction_id" in purchases.columns else 0
        
        st.write(f"- **Total Purchase Events:** {total_purchases:,}")
        st.write(f"- **Purchases with NULL Revenue:** {null_rev:,} ({null_rev / total_purchases * 100:.1f}%)")
        st.write(f"- **Purchases Missing Transaction ID:** {missing_tid:,} ({missing_tid / total_purchases * 100:.1f}%)")
        
        if null_rev > 0:
            st.warning("⚠️ Revenue totals exclude purchases where revenue is NULL to avoid misrepresenting missing values as zero.")
        else:
            st.success("✅ All recorded purchase events include valid revenue values.")

with col_r2:
    st.markdown("##### Revenue Distribution & Anomaly Threshold")
    if "revenue" in df.columns and not df.loc[df["event_name"] == "purchase", "revenue"].dropna().empty:
        rev_series = df.loc[df["event_name"] == "purchase", "revenue"].dropna()
        mean_rev = rev_series.mean()
        std_rev = rev_series.std()
        max_rev = rev_series.max()
        
        st.write(f"- **Mean Order Revenue:** ${mean_rev:,.2f}")
        st.write(f"- **Std Deviation:** ${std_rev:,.2f}")
        st.write(f"- **Max Observed Order:** ${max_rev:,.2f}")
        
        outliers = (rev_series > (mean_rev + 3.5 * std_rev)).sum()
        if outliers > 0:
            st.info(f"ℹ️ {outliers} transaction(s) exceed 3.5 standard deviations from the mean. Check whether these reflect bulk orders or data entry anomalies.")
        else:
            st.write("✅ No extreme statistical revenue outliers (> 3.5σ) detected.")
    else:
        st.write("No purchase revenue data available.")

st.markdown("---")

# ── Export Quality Report ─────────────────────────────────────────────────────
st.subheader("Export Quality Assessment")

col_e1, col_e2 = st.columns([1, 4])
with col_e1:
    csv_bytes = report_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download Report (CSV)",
        data=csv_bytes,
        file_name="growthlens_data_quality_report.csv",
        mime="text/csv",
        use_container_width=True,
    )

with st.expander("📖 Methodology Note: Expected vs. Unacceptable Missing Data in GA4"):
    st.markdown("""
    In GA4 ecommerce event tracking, not all missing values indicate a defect:
    
    1. **Expected Missing Values:**
       - `session_id` on offline or server-side measurement protocol events.
       - `transaction_id` and `revenue` on non-purchase events (`page_view`, `view_item`, etc.).
       - `traffic_source` / `traffic_medium` on direct navigation (which default to `(none)` or `direct`).
    
    2. **Unacceptable Defects:**
       - Missing `user_pseudo_id`: Prevents user-level and session-level analysis.
       - Missing `event_date` or unparseable `event_timestamp`: Prevents cohort and temporal sequence analysis.
       - Missing `revenue` on verified `purchase` events: Causes under-reported GMV or distorted average order value.
       - Duplicate candidate records: Can artificially inflate event counts if tracking scripts fire multiple times.
    """)
