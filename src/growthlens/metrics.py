"""
Core metric calculations for GrowthLens.

All functions accept a canonical events DataFrame and return scalar values
or simple DataFrames. Each metric is documented with its definition,
numerator, denominator, and NULL-handling approach.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_rate(numerator: int | float, denominator: int | float) -> Optional[float]:
    """Return numerator/denominator or None when denominator is zero."""
    if denominator == 0 or pd.isna(denominator):
        return None
    return numerator / denominator


def _pct(rate: Optional[float]) -> Optional[float]:
    """Convert a 0–1 rate to a percentage, or None."""
    if rate is None:
        return None
    return round(rate * 100, 2)


# ── Session construction ──────────────────────────────────────────────────────

def build_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate event-level data to session-level summary.

    A valid session requires both user_pseudo_id and session_id. Sessions
    missing either identifier are excluded and their count is logged.

    Returns
    -------
    pd.DataFrame with one row per (session_key), columns:
        session_key, user_pseudo_id, session_id, device_category,
        traffic_source, traffic_medium, traffic_campaign,
        session_start_ts, session_end_ts, n_events,
        has_view_item, has_add_to_cart, has_begin_checkout, has_purchase,
        revenue, transaction_id
    """
    required = {"user_pseudo_id", "session_key"}
    for col in required:
        if col not in df.columns:
            raise ValueError(f"build_sessions: missing column '{col}'")

    # Drop rows without a valid session_key
    invalid = df["session_key"].isna() | (df["session_key"] == "nan_nan")
    n_invalid = invalid.sum()
    if n_invalid:
        logger.warning("Dropping %d events with invalid session_key.", n_invalid)
    df = df[~invalid].copy()

    optional_aggs = {
        "user_pseudo_id":   ("user_pseudo_id",   "first"),
        "session_id":       ("session_id",       "first"),
        "device_category":  ("device_category",  "first"),
        "traffic_source":   ("traffic_source",   "first"),
        "traffic_medium":   ("traffic_medium",   "first"),
        "traffic_campaign": ("traffic_campaign", "first"),
        "transaction_id":   ("transaction_id",   "first"),
    }

    agg: dict = {"n_events": ("event_name", "count")}
    for target_col, (source_col, func) in optional_aggs.items():
        if source_col in df.columns:
            agg[target_col] = (source_col, func)

    if "revenue" in df.columns:
        agg["revenue"] = ("revenue", "sum")

    if "event_timestamp" in df.columns:
        agg["session_start_ts"] = ("event_timestamp", "min")
        agg["session_end_ts"]   = ("event_timestamp", "max")
    if "event_date" in df.columns:
        agg["event_date"]       = ("event_date",       "first")

    sessions = df.groupby("session_key", as_index=False).agg(**agg)

    # Ensure expected columns exist
    for col in optional_aggs:
        if col not in sessions.columns:
            sessions[col] = None

    # Add funnel flags efficiently
    funnel_map = {
        "has_view_item":      "view_item",
        "has_add_to_cart":    "add_to_cart",
        "has_begin_checkout": "begin_checkout",
        "has_purchase":       "purchase",
    }
    for flag_col, ev_name in funnel_map.items():
        sess_with_event = set(df.loc[df["event_name"] == ev_name, "session_key"].dropna())
        sessions[flag_col] = sessions["session_key"].isin(sess_with_event)

    # Revenue: NULL → 0 for non-purchasing sessions; keep NULL for purchasers
    # when it genuinely wasn't recorded (don't fabricate zeros on purchases)
    if "revenue" in sessions.columns:
        sessions["revenue"] = np.where(
            sessions["has_purchase"] & sessions["revenue"].isna(),
            np.nan,   # purchasing session with missing revenue — flag, don't zero
            sessions["revenue"].fillna(0.0),
        )
    else:
        sessions["revenue"] = 0.0

    return sessions


# ── Core KPI functions ────────────────────────────────────────────────────────

def count_unique_users(df: pd.DataFrame) -> int:
    """Count pseudonymous users (user_pseudo_id)."""
    return int(df["user_pseudo_id"].nunique())


def count_valid_sessions(sessions: pd.DataFrame) -> int:
    """Count valid sessions (rows in the sessions frame)."""
    return len(sessions)


def count_total_events(df: pd.DataFrame) -> int:
    return len(df)


def session_conversion_rate(sessions: pd.DataFrame) -> Optional[float]:
    """
    Session-based overall conversion rate.

    Definition: sessions with purchase / total valid sessions.
    Returns None when denominator is zero.
    """
    total = len(sessions)
    purchased = sessions["has_purchase"].sum()
    return _safe_rate(purchased, total)


def stage_conversion_rates(sessions: pd.DataFrame) -> dict:
    """
    Step-by-step funnel conversion rates.

    Returns a dict with keys for each adjacent stage pair and overall.
    """
    total = len(sessions)
    n_view = sessions["has_view_item"].sum()
    n_cart = sessions["has_add_to_cart"].sum()
    n_checkout = sessions["has_begin_checkout"].sum()
    n_purchase = sessions["has_purchase"].sum()

    return {
        "total_sessions":    total,
        "sessions_view":     int(n_view),
        "sessions_cart":     int(n_cart),
        "sessions_checkout": int(n_checkout),
        "sessions_purchase": int(n_purchase),
        "rate_view_to_cart":      _pct(_safe_rate(n_cart, n_view)),
        "rate_cart_to_checkout":  _pct(_safe_rate(n_checkout, n_cart)),
        "rate_checkout_to_purchase": _pct(_safe_rate(n_purchase, n_checkout)),
        "rate_overall_view_to_purchase": _pct(_safe_rate(n_purchase, n_view)),
        "rate_session_to_purchase": _pct(_safe_rate(n_purchase, total)),
    }


def total_revenue(sessions: pd.DataFrame) -> Optional[float]:
    """
    Sum purchase revenue across purchasing sessions.

    Returns None when no revenue data is present.
    Purchasing sessions with NULL revenue are excluded (not counted as zero).
    """
    if "revenue" not in sessions.columns:
        return None
    purchase_sessions = sessions[sessions["has_purchase"]]
    if purchase_sessions.empty:
        return None
    rev = purchase_sessions["revenue"].dropna()
    if rev.empty:
        return None
    return float(rev.sum())


def revenue_per_purchasing_session(sessions: pd.DataFrame) -> Optional[float]:
    """Average revenue across purchasing sessions (excluding NULL revenue)."""
    purchase_sessions = sessions[sessions["has_purchase"]]
    if purchase_sessions.empty:
        return None
    rev = purchase_sessions["revenue"].dropna()
    if rev.empty:
        return None
    return float(rev.mean())


def daily_trends(df: pd.DataFrame) -> pd.DataFrame:
    """
    Daily aggregated metrics.

    Returns DataFrame: event_date, unique_users, total_events, purchases, revenue.
    """
    daily = (
        df.groupby("event_date")
        .agg(
            unique_users=("user_pseudo_id", "nunique"),
            total_events=("event_name", "count"),
            purchases=("event_name", lambda x: (x == "purchase").sum()),
        )
        .reset_index()
    )
    if "revenue" in df.columns:
        rev_daily = (
            df[df["event_name"] == "purchase"]
            .groupby("event_date")["revenue"]
            .sum()
            .reset_index()
            .rename(columns={"revenue": "daily_revenue"})
        )
        daily = daily.merge(rev_daily, on="event_date", how="left")
        daily["daily_revenue"] = daily["daily_revenue"].fillna(0.0)

    daily["event_date"] = pd.to_datetime(daily["event_date"])
    return daily.sort_values("event_date").reset_index(drop=True)


def device_breakdown(sessions: pd.DataFrame) -> pd.DataFrame:
    """Session counts and conversion rates grouped by device_category."""
    if "device_category" not in sessions.columns:
        return pd.DataFrame()

    grp = (
        sessions.groupby("device_category")
        .agg(
            sessions=("session_key", "count"),
            sessions_view=("has_view_item", "sum"),
            sessions_cart=("has_add_to_cart", "sum"),
            sessions_checkout=("has_begin_checkout", "sum"),
            sessions_purchase=("has_purchase", "sum"),
        )
        .reset_index()
    )
    grp["conversion_rate_pct"] = (
        grp["sessions_purchase"] / grp["sessions"] * 100
    ).round(2)
    return grp.sort_values("sessions", ascending=False)


def acquisition_breakdown(sessions: pd.DataFrame) -> pd.DataFrame:
    """Session counts and conversion rates grouped by traffic_source."""
    if "traffic_source" not in sessions.columns:
        return pd.DataFrame()

    grp = (
        sessions.groupby(["traffic_source", "traffic_medium"])
        .agg(
            sessions=("session_key", "count"),
            sessions_view=("has_view_item", "sum"),
            sessions_cart=("has_add_to_cart", "sum"),
            sessions_checkout=("has_begin_checkout", "sum"),
            sessions_purchase=("has_purchase", "sum"),
        )
        .reset_index()
    )
    grp["conversion_rate_pct"] = (
        grp["sessions_purchase"] / grp["sessions"] * 100
    ).round(2)
    return grp.sort_values("sessions", ascending=False)
