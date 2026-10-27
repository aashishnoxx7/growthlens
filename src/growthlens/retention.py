"""
Cohort retention analysis for GrowthLens.

Cohort definition: the calendar WEEK of a user's first observed event
in the selected dataset. This is the first-observed-activity cohort,
NOT a verified account-signup cohort.

Retention is measured weekly: a user is "retained" in week W if they
had any event in the W-th week after their cohort week.

Important limitations:
  - The dataset covers Nov 2020 – Jan 2021 (≈13 weeks).
  - Recent cohorts have fewer observable follow-up weeks.
  - Immature cohort cells are marked as unavailable, not zero.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ── Cohort assignment ─────────────────────────────────────────────────────────

def assign_cohorts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign each user to their first-observed-activity cohort week.

    Adds column 'cohort_week' (ISO week start date as string 'YYYY-MM-DD').
    """
    if "user_pseudo_id" not in df.columns or "event_timestamp" not in df.columns:
        raise ValueError("assign_cohorts: requires 'user_pseudo_id' and 'event_timestamp'.")

    ts = pd.to_datetime(df["event_timestamp"], utc=True)
    df = df.copy()
    df["event_timestamp"] = ts
    df["_week_start"] = ts.dt.to_period("W").dt.start_time

    first_week = (
        df.groupby("user_pseudo_id")["_week_start"]
        .min()
        .rename("cohort_week")
    )
    df = df.merge(first_week, on="user_pseudo_id", how="left")
    df["_event_week"] = ts.dt.to_period("W").dt.start_time
    df["week_offset"] = (
        (df["_event_week"] - df["cohort_week"]).dt.days // 7
    ).clip(lower=0)
    df = df.drop(columns=["_week_start", "_event_week"])
    return df


def build_retention_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a cohort × week retention matrix.

    Returns
    -------
    pd.DataFrame  (index = cohort_week, columns = week_offset integers)
        Values are RETENTION RATES (0–100%), NaN for immature/unavailable cells.

    Also sets attribute .cohort_sizes (Series: cohort_week → n_users).
    """
    if "cohort_week" not in df.columns:
        df = assign_cohorts(df)

    # Count distinct users per (cohort_week, week_offset)
    active = (
        df.groupby(["cohort_week", "week_offset"])["user_pseudo_id"]
        .nunique()
        .reset_index(name="active_users")
    )

    # Cohort sizes = week 0 users
    cohort_sizes = (
        active[active["week_offset"] == 0]
        .set_index("cohort_week")["active_users"]
        .rename("cohort_size")
    )

    # Pivot to matrix
    matrix = active.pivot(
        index="cohort_week", columns="week_offset", values="active_users"
    )
    matrix = matrix.sort_index()

    # Identify immature cells: a cell (cohort, week W) is immature when
    # cohort_week + W*7 days > max observed date in the dataset.
    max_date = pd.to_datetime(df["event_timestamp"].max(), utc=True)
    if pd.isna(max_date):
        max_date = pd.Timestamp.now(tz="UTC")

    retention_pct = pd.DataFrame(index=matrix.index, columns=matrix.columns, dtype=float)
    for cohort_week in matrix.index:
        cohort_size = cohort_sizes.get(cohort_week, np.nan)
        if cohort_size == 0 or pd.isna(cohort_size):
            continue
        for week_offset in matrix.columns:
            n_active = matrix.loc[cohort_week, week_offset]
            # Is this cell observable?
            cell_start = pd.to_datetime(cohort_week, utc=True) + pd.Timedelta(days=week_offset * 7)
            if cell_start > max_date and pd.isna(n_active):
                retention_pct.loc[cohort_week, week_offset] = np.nan  # immature
            else:
                retention_pct.loc[cohort_week, week_offset] = (
                    round(n_active / cohort_size * 100, 1)
                    if pd.notna(n_active)
                    else 0.0
                )

    retention_pct.attrs["cohort_sizes"] = cohort_sizes
    # Also support attribute access if accessed directly
    try:
        object.__setattr__(retention_pct, "cohort_sizes", cohort_sizes)
    except Exception:
        pass
    return retention_pct


def retention_summary(retention_pct: pd.DataFrame) -> dict:
    """Return aggregate retention statistics from the matrix."""
    if retention_pct.empty:
        return {}

    result: dict = {}
    for week in retention_pct.columns:
        col = retention_pct[week].dropna()
        if not col.empty:
            result[f"avg_w{week}_retention"] = round(col.mean(), 1)
            result[f"n_cohorts_w{week}"] = int(col.count())

    # Best and worst cohort by week-4 retention (if available)
    if 4 in retention_pct.columns:
        col4 = retention_pct[4].dropna()
        if not col4.empty:
            result["best_cohort_w4"] = str(col4.idxmax())
            result["worst_cohort_w4"] = str(col4.idxmin())
            result["best_cohort_w4_rate"] = float(col4.max())
            result["worst_cohort_w4_rate"] = float(col4.min())

    return result
