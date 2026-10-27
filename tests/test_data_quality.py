"""
Tests for growthlens.data_quality module.
Verifies all 12 data quality integrity checks and summary aggregation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

from growthlens.data_quality import (
    check_duplicate_events,
    check_invalid_session_keys,
    check_invalid_timestamps,
    check_missing_event_date,
    check_missing_session_id,
    check_missing_transaction_ids,
    check_missing_user_id,
    check_purchase_revenue,
    check_revenue_outliers,
    check_temporal_sequence,
    quality_summary,
    run_all_quality_checks,
)


@pytest.fixture
def clean_events_df():
    return pd.DataFrame([
        {
            "event_date": "2020-11-01",
            "event_timestamp": pd.Timestamp("2020-11-01 10:00:00", tz="UTC"),
            "event_name": "view_item",
            "user_pseudo_id": "u1",
            "session_id": "1001",
            "session_key": "u1_1001",
            "device_category": "desktop",
            "traffic_source": "google",
            "revenue": None,
            "transaction_id": None,
        },
        {
            "event_date": "2020-11-01",
            "event_timestamp": pd.Timestamp("2020-11-01 10:05:00", tz="UTC"),
            "event_name": "purchase",
            "user_pseudo_id": "u1",
            "session_id": "1001",
            "session_key": "u1_1001",
            "device_category": "desktop",
            "traffic_source": "google",
            "revenue": 45.0,
            "transaction_id": "T123",
        },
    ])


def test_check_missing_user_id_detects_nulls(clean_events_df):
    df_corrupted = clean_events_df.copy()
    df_corrupted.loc[0, "user_pseudo_id"] = None
    res = check_missing_user_id(df_corrupted)
    assert res["status"] == "fail"
    assert res["affected_rows"] == 1


def test_check_missing_event_date(clean_events_df):
    df_corrupted = clean_events_df.copy()
    df_corrupted.loc[1, "event_date"] = None
    res = check_missing_event_date(df_corrupted)
    assert res["status"] == "warn" or res["status"] == "fail"
    assert res["affected_rows"] == 1


def test_check_invalid_timestamps_detects_unparseable(clean_events_df):
    df = clean_events_df.copy()
    df["event_timestamp"] = ["invalid_date_str", "2020-11-01 10:05:00"]
    res = check_invalid_timestamps(df)
    assert res["affected_rows"] >= 1


def test_check_duplicate_events(clean_events_df):
    # Duplicate row 0
    df = pd.concat([clean_events_df, clean_events_df.iloc[[0]]], ignore_index=True)
    res = check_duplicate_events(df)
    assert res["affected_rows"] == 1


def test_check_purchase_revenue_null(clean_events_df):
    df = clean_events_df.copy()
    # Set purchase event revenue to NULL
    df.loc[df["event_name"] == "purchase", "revenue"] = None
    res = check_purchase_revenue(df)
    assert res["affected_rows"] == 1
    assert res["status"] in ("warn", "fail")


def test_check_purchase_revenue_clean(clean_events_df):
    res = check_purchase_revenue(clean_events_df)
    assert res["affected_rows"] == 0
    assert res["status"] == "pass"


def test_check_missing_transaction_ids(clean_events_df):
    df = clean_events_df.copy()
    df.loc[df["event_name"] == "purchase", "transaction_id"] = None
    res = check_missing_transaction_ids(df)
    assert res["affected_rows"] == 1
    assert res["status"] in ("warn", "fail")


def test_purchase_check_only_on_purchase_events(clean_events_df):
    # Non-purchase events having null transaction_id shouldn't be counted in missing_transaction_ids
    res = check_missing_transaction_ids(clean_events_df)
    assert res["affected_rows"] == 0
    assert res["status"] == "pass"


def test_check_revenue_outliers():
    # 20 normal purchases + 1 extreme outlier
    revs = [20.0 + i for i in range(20)] + [1_000_000.0]
    df = pd.DataFrame({
        "event_name": ["purchase"] * len(revs),
        "revenue": revs,
    })
    res = check_revenue_outliers(df)
    assert res["affected_rows"] >= 1


def test_run_all_quality_checks_returns_list(clean_events_df):
    checks = run_all_quality_checks(clean_events_df)
    assert isinstance(checks, list)
    assert len(checks) == 12
    summary = quality_summary(checks)
    assert "total_checks" in summary
    assert summary["total_checks"] == 12
    assert summary["overall_status"] == "pass"
