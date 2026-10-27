"""
Acquisition-channel analysis for GrowthLens.

Important: GA4's traffic_source fields describe FIRST-USER acquisition,
not session-level attribution. This module clearly labels that distinction.
"""

from __future__ import annotations

import logging

import pandas as pd

from growthlens.config import MIN_SEGMENT_SIZE

logger = logging.getLogger(__name__)


def acquisition_performance(sessions: pd.DataFrame) -> pd.DataFrame:
    """
    Acquisition performance matrix by source × medium.

    Returns DataFrame with:
        traffic_source, traffic_medium, sessions, users,
        sessions_view, sessions_cart, sessions_checkout, sessions_purchase,
        conversion_rate_pct, view_rate_pct, cart_rate_pct,
        checkout_rate_pct, low_sample (bool)
    """
    if sessions.empty:
        return pd.DataFrame()

    grp_cols = [c for c in ["traffic_source", "traffic_medium"] if c in sessions.columns]
    if not grp_cols:
        return pd.DataFrame()

    agg = sessions.groupby(grp_cols).agg(
        sessions=("session_key", "count"),
        users=("user_pseudo_id", "nunique"),
        sessions_view=("has_view_item", "sum"),
        sessions_cart=("has_add_to_cart", "sum"),
        sessions_checkout=("has_begin_checkout", "sum"),
        sessions_purchase=("has_purchase", "sum"),
    ).reset_index()

    agg["view_rate_pct"]     = (agg["sessions_view"]     / agg["sessions"] * 100).round(1)
    agg["cart_rate_pct"]     = (agg["sessions_cart"]     / agg["sessions"] * 100).round(1)
    agg["checkout_rate_pct"] = (agg["sessions_checkout"] / agg["sessions"] * 100).round(1)
    agg["conversion_rate_pct"] = (agg["sessions_purchase"] / agg["sessions"] * 100).round(2)
    agg["low_sample"] = agg["sessions"] < MIN_SEGMENT_SIZE

    return agg.sort_values("sessions", ascending=False).reset_index(drop=True)


def device_performance(sessions: pd.DataFrame) -> pd.DataFrame:
    """Device-level performance comparison."""
    if "device_category" not in sessions.columns:
        return pd.DataFrame()

    agg = sessions.groupby("device_category").agg(
        sessions=("session_key", "count"),
        users=("user_pseudo_id", "nunique"),
        sessions_view=("has_view_item", "sum"),
        sessions_cart=("has_add_to_cart", "sum"),
        sessions_checkout=("has_begin_checkout", "sum"),
        sessions_purchase=("has_purchase", "sum"),
    ).reset_index()

    agg["conversion_rate_pct"] = (agg["sessions_purchase"] / agg["sessions"] * 100).round(2)
    agg["low_sample"] = agg["sessions"] < MIN_SEGMENT_SIZE
    return agg.sort_values("sessions", ascending=False).reset_index(drop=True)


def acquisition_findings(acq_df: pd.DataFrame, overall_rate: float) -> list[dict]:
    """
    Rule-based findings for acquisition analysis.
    Returns list of finding dicts.
    """
    findings = []
    if acq_df.empty:
        return findings

    # High volume but below-average conversion
    high_volume = acq_df[acq_df["sessions"] >= MIN_SEGMENT_SIZE * 5]
    for _, row in high_volume.iterrows():
        if row["conversion_rate_pct"] < overall_rate * 100 * 0.7:
            src = f"{row.get('traffic_source', '?')} / {row.get('traffic_medium', '?')}"
            findings.append({
                "type": "high_volume_low_conversion",
                "severity": "medium",
                "message": (
                    f"'{src}' drives {int(row['sessions']):,} sessions but converts at "
                    f"{row['conversion_rate_pct']:.1f}% vs overall {overall_rate*100:.1f}%. "
                    "Investigate traffic intent and landing-page relevance."
                ),
                "evidence": {
                    "source": src,
                    "sessions": int(row["sessions"]),
                    "conversion_rate": float(row["conversion_rate_pct"]),
                    "overall_rate": round(overall_rate * 100, 2),
                },
            })

    return findings
