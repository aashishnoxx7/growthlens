"""
Session-based conversion funnel analysis for GrowthLens.

Funnel stages (in required temporal order):
  1. view_item         → Product Viewed
  2. add_to_cart       → Added to Cart
  3. begin_checkout    → Checkout Started
  4. purchase          → Purchase Completed

A session progresses through the funnel only if earlier stages occurred
before later ones (using event_timestamp). The FIRST valid occurrence of
each stage within the session is used.
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from growthlens.config import FUNNEL_STAGE_LABELS, FUNNEL_STAGES, MIN_SEGMENT_SIZE

logger = logging.getLogger(__name__)


# ── Core funnel logic ─────────────────────────────────────────────────────────

def compute_ordered_funnel(
    df: pd.DataFrame,
    stages: list[str] | None = None,
) -> pd.DataFrame:
    """
    Compute a session-based, temporally-ordered conversion funnel.

    For each session, the first valid event of each stage is identified.
    A session is counted at stage N only if it also reached stage N-1
    (first occurrence of N-1 must be before first occurrence of N).

    Parameters
    ----------
    df     : canonical events DataFrame (must have event_timestamp, session_key)
    stages : ordered list of event_name values (defaults to FUNNEL_STAGES)

    Returns
    -------
    pd.DataFrame with columns:
        stage, label, sessions, pct_of_first_stage, pct_of_prev_stage,
        dropoff_abs, dropoff_pct
    """
    stages = stages or FUNNEL_STAGES
    if "session_key" not in df.columns or "event_timestamp" not in df.columns:
        raise ValueError("compute_ordered_funnel requires 'session_key' and 'event_timestamp'.")

    # Drop invalid sessions
    valid = df[df["session_key"].notna() & (df["session_key"] != "nan_nan")].copy()
    valid["event_timestamp"] = pd.to_datetime(valid["event_timestamp"], utc=True)

    # For each session, find the first timestamp of each funnel stage
    funnel_events = valid[valid["event_name"].isin(stages)].copy()
    if funnel_events.empty:
        logger.warning("No funnel events found in the supplied DataFrame.")
        return _empty_funnel_df(stages)

    # First occurrence of each stage per session
    first_ts = (
        funnel_events
        .sort_values("event_timestamp")
        .groupby(["session_key", "event_name"])["event_timestamp"]
        .first()
        .unstack(level="event_name")
        .reindex(columns=stages)
    )

    # Ensure all stage columns are explicitly datetime64[ns, UTC]
    for col in stages:
        if col in first_ts.columns:
            first_ts[col] = pd.to_datetime(first_ts[col], utc=True)
        else:
            first_ts[col] = pd.Series(pd.NaT, index=first_ts.index, dtype="datetime64[ns, UTC]")

    # Enforce temporal ordering: set stage N to NaT when stage N-1 is NaT or
    # when stage N's first timestamp precedes stage N-1's timestamp.
    for i in range(1, len(stages)):
        prev = stages[i - 1]
        curr = stages[i]
        # Invalidate: curr arrives before prev, or prev was never reached
        invalid_mask = (
            first_ts[prev].isna() |
            (first_ts[curr] < first_ts[prev])
        )
        first_ts.loc[invalid_mask, curr] = pd.NaT

    # Count sessions reaching each stage
    counts = first_ts.notna().sum()

    # Build result frame
    rows = []
    for i, stage in enumerate(stages):
        n = int(counts.get(stage, 0))
        label = FUNNEL_STAGE_LABELS.get(stage, stage)
        rows.append({"stage": stage, "label": label, "sessions": n})

    result = pd.DataFrame(rows)

    first_stage_n = result.loc[0, "sessions"]
    result["pct_of_first_stage"] = (
        (result["sessions"] / first_stage_n * 100).round(2)
        if first_stage_n > 0 else None
    )

    result["pct_of_prev_stage"] = None
    for i in range(1, len(result)):
        prev_n = result.loc[i - 1, "sessions"]
        curr_n = result.loc[i, "sessions"]
        result.loc[i, "pct_of_prev_stage"] = (
            round(curr_n / prev_n * 100, 2) if prev_n > 0 else None
        )

    result["dropoff_abs"] = result["sessions"].diff(-1).shift(0)
    result["dropoff_abs"] = result["sessions"] - result["sessions"].shift(-1)
    result["dropoff_pct"] = (
        (result["dropoff_abs"] / result["sessions"] * 100)
        .round(2)
        .where(result["sessions"] > 0)
    )

    return result


def _empty_funnel_df(stages: list[str]) -> pd.DataFrame:
    rows = [
        {
            "stage": s,
            "label": FUNNEL_STAGE_LABELS.get(s, s),
            "sessions": 0,
            "pct_of_first_stage": None,
            "pct_of_prev_stage": None,
            "dropoff_abs": None,
            "dropoff_pct": None,
        }
        for s in stages
    ]
    return pd.DataFrame(rows)


# ── Segmented funnel ──────────────────────────────────────────────────────────

def compute_funnel_by_segment(
    df: pd.DataFrame,
    segment_col: str,
    stages: list[str] | None = None,
    min_sessions: int = MIN_SEGMENT_SIZE,
) -> pd.DataFrame:
    """
    Compute funnel metrics for each value of segment_col.

    Returns a DataFrame with (segment, stage, label, sessions, pct_of_prev_stage).
    Segments with fewer than min_sessions entering the funnel are flagged.
    """
    stages = stages or FUNNEL_STAGES
    if segment_col not in df.columns:
        logger.warning("Segment column '%s' not found.", segment_col)
        return pd.DataFrame()

    results = []
    for seg_val, grp in df.groupby(segment_col):
        funnel = compute_ordered_funnel(grp, stages=stages)
        funnel["segment"] = seg_val
        funnel["low_sample"] = funnel["sessions"].iloc[0] < min_sessions if len(funnel) > 0 else True
        results.append(funnel)

    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


# ── Funnel findings engine ────────────────────────────────────────────────────

def funnel_findings(
    funnel_df: pd.DataFrame,
    segmented_df: Optional[pd.DataFrame] = None,
    overall_conversion: Optional[float] = None,
) -> list[dict]:
    """
    Rule-based findings from funnel analysis.

    Returns a list of finding dicts:
        {type, severity, message, evidence}
    """
    findings: list[dict] = []

    if funnel_df.empty or funnel_df["sessions"].iloc[0] == 0:
        return findings

    # ── Largest absolute drop-off ─────────────────────────────────────────────
    interior = funnel_df.dropna(subset=["dropoff_abs"])
    if not interior.empty:
        worst = interior.loc[interior["dropoff_abs"].idxmax()]
        findings.append({
            "type": "funnel_drop",
            "severity": "high",
            "message": (
                f"The largest session loss occurs after '{worst['label']}': "
                f"{int(worst['dropoff_abs']):,} sessions do not proceed "
                f"({worst['dropoff_pct']:.1f}% drop-off). "
                "Investigate the experience at this stage."
            ),
            "evidence": {
                "stage": worst["stage"],
                "dropoff_abs": int(worst["dropoff_abs"]),
                "dropoff_pct": float(worst["dropoff_pct"]),
            },
        })

    # ── Segment conversion differences ────────────────────────────────────────
    if segmented_df is not None and not segmented_df.empty and overall_conversion is not None:
        purchase_stage = FUNNEL_STAGES[-1]
        seg_summary = (
            segmented_df[segmented_df["stage"] == purchase_stage]
            .copy()
        )
        first_stage = FUNNEL_STAGES[0]
        seg_entry = (
            segmented_df[segmented_df["stage"] == first_stage][["segment", "sessions"]]
            .rename(columns={"sessions": "entry_sessions"})
        )
        seg_summary = seg_summary.merge(seg_entry, on="segment", how="left")
        seg_summary["seg_conversion"] = (
            seg_summary["sessions"] / seg_summary["entry_sessions"] * 100
        ).round(2)

        low_conv = seg_summary[
            (seg_summary["seg_conversion"] < overall_conversion * 100 * 0.8) &
            (seg_summary["entry_sessions"] >= MIN_SEGMENT_SIZE) &
            (~seg_summary["low_sample"])
        ]
        for _, row in low_conv.iterrows():
            findings.append({
                "type": "segment_low_conversion",
                "severity": "medium",
                "message": (
                    f"Segment '{row['segment']}' shows a lower observed conversion rate "
                    f"({row['seg_conversion']:.1f}%) vs overall "
                    f"({overall_conversion * 100:.1f}%). "
                    "Inspect the funnel journey for this segment."
                ),
                "evidence": {
                    "segment": row["segment"],
                    "segment_conversion": float(row["seg_conversion"]),
                    "overall_conversion": round(overall_conversion * 100, 2),
                    "entry_sessions": int(row["entry_sessions"]),
                },
            })

    return findings
