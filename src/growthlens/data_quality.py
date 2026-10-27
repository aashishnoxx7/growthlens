"""
Data-quality checks for GrowthLens.

Each check returns a structured result dict:
    {check_name, severity, status, affected_rows, pct_affected, message, remediation}

severity: "info" | "warning" | "error"
status:   "pass" | "warn" | "fail"
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from growthlens.config import REVENUE_OUTLIER_Z

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"error": 2, "warning": 1, "info": 0}

# ── Individual check functions ────────────────────────────────────────────────

def _check(
    name: str,
    severity: str,
    affected: int,
    total: int,
    message: str,
    remediation: str,
    pass_threshold: float = 0.0,
) -> dict:
    pct = round(affected / total * 100, 2) if total > 0 else 0.0
    status = "fail" if pct > pass_threshold and severity == "error" else \
             "warn" if pct > pass_threshold else "pass"
    return {
        "check_name": name,
        "severity": severity,
        "status": status,
        "affected_rows": int(affected),
        "total_rows": int(total),
        "pct_affected": pct,
        "message": message,
        "remediation": remediation,
    }


def check_missing_user_id(df: pd.DataFrame) -> dict:
    n = df["user_pseudo_id"].isna().sum() if "user_pseudo_id" in df.columns else len(df)
    return _check(
        "missing_user_pseudo_id", "error", n, len(df),
        f"{n:,} events have no user_pseudo_id — these cannot be attributed to any user.",
        "Verify GA4 instrumentation. Events without user_pseudo_id are excluded from user metrics.",
        pass_threshold=0.0,
    )


def check_missing_event_date(df: pd.DataFrame) -> dict:
    n = df["event_date"].isna().sum() if "event_date" in df.columns else len(df)
    return _check(
        "missing_event_date", "error", n, len(df),
        f"{n:,} events have no event_date.",
        "Records without a date cannot be assigned to any time window. Investigate data pipeline.",
    )


def check_invalid_timestamps(df: pd.DataFrame) -> dict:
    if "event_timestamp" not in df.columns:
        return _check("invalid_timestamp", "warning", 0, len(df), "event_timestamp column absent.", "")
    if pd.api.types.is_datetime64_any_dtype(df["event_timestamp"]):
        n = df["event_timestamp"].isna().sum()
    else:
        parsed = pd.to_datetime(df["event_timestamp"], errors="coerce", utc=True)
        n = parsed.isna().sum()
    return _check(
        "invalid_timestamp", "error", n, len(df),
        f"{n:,} events have unparseable timestamps.",
        "Ensure event_timestamp is a UTC datetime or microsecond integer.",
    )


def check_missing_session_id(df: pd.DataFrame) -> dict:
    if "session_id" not in df.columns:
        return _check("missing_session_id", "warning", 0, len(df), "session_id column absent.", "")
    n = df["session_id"].isna().sum() + (df["session_id"] == "None").sum()
    return _check(
        "missing_session_id", "warning", n, len(df),
        f"{n:,} events have no GA4 session_id. Sessions cannot be constructed for these events.",
        "Check that ga_session_id is present in event_params for all tracked events.",
        pass_threshold=5.0,
    )


def check_invalid_session_keys(df: pd.DataFrame) -> dict:
    if "session_key" not in df.columns:
        return _check("invalid_session_key", "warning", 0, len(df), "session_key absent.", "")
    invalid = df["session_key"].isna() | df["session_key"].str.contains("nan", na=False)
    n = int(invalid.sum())
    return _check(
        "invalid_session_key", "warning", n, len(df),
        f"{n:,} events have invalid session keys (null user or session ID).",
        "These events are excluded from session-level analysis.",
        pass_threshold=5.0,
    )


def check_duplicate_events(df: pd.DataFrame) -> dict:
    """
    Flag candidate duplicate events: same (user_pseudo_id, event_timestamp, event_name).
    Does NOT delete records — legitimate duplicates exist. Returns count for investigation.
    """
    key_cols = [c for c in ["user_pseudo_id", "event_timestamp", "event_name"] if c in df.columns]
    if len(key_cols) < 3:
        return _check("duplicate_events", "info", 0, len(df), "Cannot check duplicates — missing key columns.", "")
    n_dupes = int(df.duplicated(subset=key_cols).sum())
    return _check(
        "duplicate_events", "warning" if n_dupes > 0 else "info",
        n_dupes, len(df),
        f"{n_dupes:,} candidate duplicate events (same user, timestamp, event_name). "
        "These may be legitimate re-fires or a tracking issue.",
        "Review whether deduplication is justified for your analysis. "
        "Do not blindly deduplicate — check GA4 configuration.",
        pass_threshold=1.0,
    )


def check_missing_device(df: pd.DataFrame) -> dict:
    if "device_category" not in df.columns:
        return _check("missing_device", "info", 0, len(df), "device_category absent.", "")
    n = df["device_category"].isna().sum()
    return _check(
        "missing_device", "info", n, len(df),
        f"{n:,} events lack device_category. Device segmentation will exclude these.",
        "Acceptable for server-side events. Investigate if proportion is high for client events.",
        pass_threshold=10.0,
    )


def check_unexpected_event_names(df: pd.DataFrame) -> dict:
    expected = {
        "session_start", "page_view", "view_item", "add_to_cart",
        "begin_checkout", "purchase", "user_engagement", "scroll",
        "click", "file_download", "video_start", "video_complete",
    }
    if "event_name" not in df.columns:
        return _check("unexpected_events", "info", 0, len(df), "event_name absent.", "")
    unexpected = ~df["event_name"].isin(expected)
    n = int(unexpected.sum())
    unexpected_names = df.loc[unexpected, "event_name"].value_counts().head(10).to_dict()
    return _check(
        "unexpected_event_names", "info", n, len(df),
        f"{n:,} events have event names outside the expected set. "
        f"Top unexpected: {unexpected_names}",
        "Review whether custom events are expected. Filter unexpected events if they affect analysis.",
        pass_threshold=30.0,
    )


def check_purchase_revenue(df: pd.DataFrame) -> dict:
    if "revenue" not in df.columns:
        return _check("purchase_revenue", "warning", 0, len(df), "revenue column absent.", "")
    purchase_mask = df["event_name"] == "purchase"
    purchase_events = df[purchase_mask]
    if purchase_events.empty:
        return _check("purchase_revenue", "info", 0, len(df), "No purchase events found.", "")
    null_rev = purchase_events["revenue"].isna().sum()
    return _check(
        "purchase_revenue", "error" if null_rev > 0 else "info",
        int(null_rev), len(purchase_events),
        f"{null_rev:,} purchase events have NULL revenue. "
        "Revenue totals for affected transactions are excluded.",
        "Check ecommerce.purchase_revenue_in_usd in the GA4 schema. "
        "Do not replace NULL revenue with zero without a business justification.",
    )


def check_missing_transaction_ids(df: pd.DataFrame) -> dict:
    if "transaction_id" not in df.columns:
        return _check("missing_transaction_id", "warning", 0, len(df), "transaction_id absent.", "")
    purchase_mask = df["event_name"] == "purchase"
    purchase_events = df[purchase_mask]
    if purchase_events.empty:
        return _check("missing_transaction_id", "info", 0, len(df), "No purchase events.", "")
    n = purchase_events["transaction_id"].isna().sum()
    return _check(
        "missing_transaction_id", "warning", int(n), len(purchase_events),
        f"{n:,} purchase events lack a transaction_id. Revenue deduplication is not possible for these.",
        "Ensure ecommerce.transaction_id is populated by your GA4 implementation.",
        pass_threshold=1.0,
    )


def check_revenue_outliers(df: pd.DataFrame) -> dict:
    if "revenue" not in df.columns:
        return _check("revenue_outliers", "info", 0, len(df), "revenue absent.", "")
    rev = df.loc[df["event_name"] == "purchase", "revenue"].dropna()
    if rev.empty or rev.std() == 0:
        return _check("revenue_outliers", "info", 0, len(df), "Insufficient revenue data.", "")
    z_scores = (rev - rev.mean()) / rev.std()
    outliers = (z_scores.abs() > REVENUE_OUTLIER_Z).sum()
    return _check(
        "revenue_outliers", "warning" if outliers > 0 else "info",
        int(outliers), len(rev),
        f"{outliers:,} purchase events have revenue beyond {REVENUE_OUTLIER_Z} standard deviations "
        f"(mean={rev.mean():.2f}, std={rev.std():.2f}). "
        "These may be legitimate high-value orders or data errors.",
        "Review outlier records individually. Do not remove without business justification.",
        pass_threshold=1.0,
    )


def check_temporal_sequence(df: pd.DataFrame) -> dict:
    """
    Check for sessions where purchase timestamp precedes view_item timestamp.
    """
    if "session_key" not in df.columns or "event_timestamp" not in df.columns:
        return _check("temporal_sequence", "info", 0, len(df), "Cannot check — missing columns.", "")

    purchase_ts = (
        df[df["event_name"] == "purchase"]
        .groupby("session_key")["event_timestamp"].min()
    )
    view_ts = (
        df[df["event_name"] == "view_item"]
        .groupby("session_key")["event_timestamp"].min()
    )
    common = purchase_ts.index.intersection(view_ts.index)
    if common.empty:
        return _check("temporal_sequence", "info", 0, len(df), "No sessions with both view_item and purchase.", "")

    bad = (purchase_ts[common] < view_ts[common]).sum()
    return _check(
        "temporal_sequence", "warning" if bad > 0 else "info",
        int(bad), len(common),
        f"{bad:,} sessions have a purchase timestamp before view_item timestamp. "
        "This may indicate timestamp inconsistency or tracking issues.",
        "Review whether GA4 event_timestamp is being set correctly. "
        "These sessions are excluded from ordered funnel analysis.",
        pass_threshold=0.5,
    )


# ── Run all checks ────────────────────────────────────────────────────────────

def run_all_quality_checks(df: pd.DataFrame) -> list[dict]:
    """Run all data-quality checks and return sorted results."""
    checks = [
        check_missing_user_id(df),
        check_missing_event_date(df),
        check_invalid_timestamps(df),
        check_missing_session_id(df),
        check_invalid_session_keys(df),
        check_duplicate_events(df),
        check_missing_device(df),
        check_unexpected_event_names(df),
        check_purchase_revenue(df),
        check_missing_transaction_ids(df),
        check_revenue_outliers(df),
        check_temporal_sequence(df),
    ]
    # Sort by severity (errors first)
    return sorted(checks, key=lambda x: SEVERITY_RANK.get(x["severity"], 0), reverse=True)


def quality_summary(checks: list[dict]) -> dict:
    """Aggregate quality check results into a summary."""
    total = len(checks)
    errors = sum(1 for c in checks if c["severity"] == "error" and c["status"] in ("warn", "fail"))
    warnings = sum(1 for c in checks if c["severity"] == "warning" and c["status"] in ("warn", "fail"))
    passes = sum(1 for c in checks if c["status"] == "pass")
    return {
        "total_checks": total,
        "errors": errors,
        "warnings": warnings,
        "passes": passes,
        "overall_status": "fail" if errors > 0 else "warn" if warnings > 0 else "pass",
    }
