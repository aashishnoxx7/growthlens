"""
Schema definitions and validation for GrowthLens event records.

The canonical event DataFrame has the following columns after transformation.
Any source (BigQuery, local file, synthetic) must produce this shape before
the analytical layer touches it.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ── Column specifications ─────────────────────────────────────────────────────

# Required columns that every source must supply
REQUIRED_COLUMNS = {
    "event_date",           # date  (YYYY-MM-DD string → parsed to date)
    "event_timestamp",      # int64 microseconds since epoch → parsed to datetime
    "event_name",           # str
    "user_pseudo_id",       # str  (GA4 pseudonymous identifier)
}

# Optional but used for analysis; missing values are tolerated
OPTIONAL_COLUMNS = {
    "session_id",           # str/int  GA4 ga_session_id event param
    "session_key",          # str  f"{user_pseudo_id}_{session_id}"
    "device_category",      # str  mobile | tablet | desktop
    "traffic_source",       # str  first-user acquisition source
    "traffic_medium",       # str  first-user acquisition medium
    "traffic_campaign",     # str  first-user campaign name
    "revenue",              # float  purchase_revenue_in_usd
    "transaction_id",       # str
    "page_location",        # str
    "item_name",            # str  (from items array — may be multi-row)
    "item_id",              # str
    "item_revenue",         # float
}

CANONICAL_DTYPES: dict[str, str] = {
    "event_date":       "object",    # str 'YYYY-MM-DD'
    "event_name":       "object",
    "user_pseudo_id":   "object",
    "session_id":       "object",
    "session_key":      "object",
    "device_category":  "object",
    "traffic_source":   "object",
    "traffic_medium":   "object",
    "traffic_campaign": "object",
    "transaction_id":   "object",
    "page_location":    "object",
    "item_name":        "object",
    "item_id":          "object",
}

# ── Validation ────────────────────────────────────────────────────────────────

class SchemaValidationError(ValueError):
    """Raised when an uploaded or generated DataFrame fails schema checks."""


def validate_events_df(df: pd.DataFrame, source_label: str = "data") -> list[str]:
    """
    Validate *df* against the canonical schema.

    Returns a list of human-readable warning strings (empty = all OK).
    Raises SchemaValidationError for fatal problems (missing required columns,
    completely empty frame).
    """
    warnings: list[str] = []

    if df.empty:
        raise SchemaValidationError(f"{source_label}: DataFrame is empty.")

    # ── Required columns ─────────────────────────────────────────────────────
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise SchemaValidationError(
            f"{source_label}: Missing required columns: {sorted(missing)}"
        )

    # ── event_date ────────────────────────────────────────────────────────────
    null_dates = df["event_date"].isna().sum()
    if null_dates:
        warnings.append(f"{null_dates:,} rows have NULL event_date.")

    # ── event_timestamp ───────────────────────────────────────────────────────
    if "event_timestamp" in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df["event_timestamp"]):
            try:
                pd.to_datetime(df["event_timestamp"], unit="us", errors="coerce")
            except Exception:
                warnings.append("event_timestamp could not be parsed.")

    # ── user_pseudo_id ────────────────────────────────────────────────────────
    null_uid = df["user_pseudo_id"].isna().sum()
    if null_uid:
        warnings.append(f"{null_uid:,} rows have NULL user_pseudo_id.")

    # ── event_name ────────────────────────────────────────────────────────────
    if df["event_name"].isna().any():
        warnings.append("Some rows have NULL event_name.")

    # ── revenue ───────────────────────────────────────────────────────────────
    if "revenue" in df.columns:
        purchase_mask = df["event_name"] == "purchase"
        null_rev = df.loc[purchase_mask, "revenue"].isna().sum()
        if null_rev:
            warnings.append(
                f"{null_rev:,} purchase events have NULL revenue — "
                "revenue totals will exclude those transactions."
            )
        neg_rev = (df.loc[purchase_mask, "revenue"].fillna(0) < 0).sum()
        if neg_rev:
            warnings.append(f"{neg_rev:,} purchase events have negative revenue.")

    logger.info(
        "Schema validation for '%s': %d rows, %d warnings.",
        source_label, len(df), len(warnings),
    )
    return warnings


def coerce_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Apply safe type coercions to a canonical events DataFrame in-place."""
    df = df.copy()

    # Timestamps: accept microsecond integers or ISO strings
    if "event_timestamp" in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df["event_timestamp"]):
            # Try numeric microseconds first, then strings
            ts = pd.to_numeric(df["event_timestamp"], errors="coerce")
            if ts.notna().any():
                df["event_timestamp"] = pd.to_datetime(ts, unit="us", utc=True, errors="coerce")
            else:
                df["event_timestamp"] = pd.to_datetime(
                    df["event_timestamp"], utc=True, errors="coerce"
                )

    # Revenue to float
    for col in ("revenue", "item_revenue"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # session_id: keep as string (GA4 IDs can look numeric but shouldn't be summed)
    if "session_id" in df.columns:
        df["session_id"] = df["session_id"].astype(str).replace("nan", None)

    # Object columns → explicit str or None
    for col in CANONICAL_DTYPES:
        if col in df.columns and CANONICAL_DTYPES[col] == "object":
            df[col] = df[col].where(df[col].notna(), other=None)

    return df
