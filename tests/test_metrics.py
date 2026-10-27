"""
Tests for growthlens.metrics module.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

from growthlens.metrics import (
    build_sessions,
    count_total_events,
    count_unique_users,
    count_valid_sessions,
    daily_trends,
    device_breakdown,
    revenue_per_purchasing_session,
    session_conversion_rate,
    stage_conversion_rates,
    total_revenue,
)


@pytest.fixture
def sample_events_df():
    """Hand-crafted canonical events DataFrame for testing metrics."""
    return pd.DataFrame([
        {
            "event_date": "2020-11-01",
            "event_timestamp": pd.Timestamp("2020-11-01 10:00:00", tz="UTC"),
            "event_name": "view_item",
            "user_pseudo_id": "u1",
            "session_id": "s1",
            "session_key": "u1_s1",
            "device_category": "desktop",
            "traffic_source": "google",
            "traffic_medium": "organic",
            "revenue": None,
            "transaction_id": None,
        },
        {
            "event_date": "2020-11-01",
            "event_timestamp": pd.Timestamp("2020-11-01 10:05:00", tz="UTC"),
            "event_name": "add_to_cart",
            "user_pseudo_id": "u1",
            "session_id": "s1",
            "session_key": "u1_s1",
            "device_category": "desktop",
            "traffic_source": "google",
            "traffic_medium": "organic",
            "revenue": None,
            "transaction_id": None,
        },
        {
            "event_date": "2020-11-01",
            "event_timestamp": pd.Timestamp("2020-11-01 10:10:00", tz="UTC"),
            "event_name": "purchase",
            "user_pseudo_id": "u1",
            "session_id": "s1",
            "session_key": "u1_s1",
            "device_category": "desktop",
            "traffic_source": "google",
            "traffic_medium": "organic",
            "revenue": 50.0,
            "transaction_id": "t1",
        },
        {
            "event_date": "2020-11-01",
            "event_timestamp": pd.Timestamp("2020-11-01 11:00:00", tz="UTC"),
            "event_name": "view_item",
            "user_pseudo_id": "u2",
            "session_id": "s2",
            "session_key": "u2_s2",
            "device_category": "mobile",
            "traffic_source": "direct",
            "traffic_medium": "(none)",
            "revenue": None,
            "transaction_id": None,
        },
        {
            "event_date": "2020-11-02",
            "event_timestamp": pd.Timestamp("2020-11-02 09:00:00", tz="UTC"),
            "event_name": "view_item",
            "user_pseudo_id": "u3",
            "session_id": "s3",
            "session_key": "u3_s3",
            "device_category": "tablet",
            "traffic_source": "facebook",
            "traffic_medium": "cpc",
            "revenue": None,
            "transaction_id": None,
        },
        {
            "event_date": "2020-11-02",
            "event_timestamp": pd.Timestamp("2020-11-02 09:15:00", tz="UTC"),
            "event_name": "purchase",
            "user_pseudo_id": "u3",
            "session_id": "s3",
            "session_key": "u3_s3",
            "device_category": "tablet",
            "traffic_source": "facebook",
            "traffic_medium": "cpc",
            "revenue": 100.0,
            "transaction_id": "t2",
        },
    ])


def test_count_unique_users_basic(sample_events_df):
    assert count_unique_users(sample_events_df) == 3


def test_count_unique_users_empty():
    empty_df = pd.DataFrame(columns=["user_pseudo_id"])
    assert count_unique_users(empty_df) == 0


def test_build_sessions_valid(sample_events_df):
    sessions = build_sessions(sample_events_df)
    assert count_valid_sessions(sessions) == 3
    assert set(sessions["session_key"]) == {"u1_s1", "u2_s2", "u3_s3"}
    assert "has_purchase" in sessions.columns
    assert sessions.loc[sessions["session_key"] == "u1_s1", "has_purchase"].iloc[0] == True
    assert sessions.loc[sessions["session_key"] == "u2_s2", "has_purchase"].iloc[0] == False


def test_build_sessions_drops_invalid_session_key():
    df = pd.DataFrame([
        {"user_pseudo_id": "u1", "session_key": None, "event_name": "page_view"},
        {"user_pseudo_id": "u1", "session_key": "nan_nan", "event_name": "page_view"},
        {"user_pseudo_id": "u2", "session_key": "u2_s1", "event_name": "page_view"},
    ])
    sessions = build_sessions(df)
    assert len(sessions) == 1
    assert sessions["session_key"].iloc[0] == "u2_s1"


def test_session_conversion_rate_no_purchases():
    sessions = pd.DataFrame({
        "session_key": ["s1", "s2"],
        "has_purchase": [False, False],
    })
    assert session_conversion_rate(sessions) == 0.0


def test_session_conversion_rate_all_purchase():
    sessions = pd.DataFrame({
        "session_key": ["s1", "s2"],
        "has_purchase": [True, True],
    })
    assert session_conversion_rate(sessions) == 1.0


def test_session_conversion_rate_zero_sessions():
    sessions = pd.DataFrame(columns=["session_key", "has_purchase"])
    assert session_conversion_rate(sessions) is None


def test_total_revenue_sums_correctly():
    sessions = pd.DataFrame({
        "has_purchase": [True, True, False],
        "revenue": [50.0, 75.50, 0.0],
    })
    assert total_revenue(sessions) == pytest.approx(125.50)


def test_total_revenue_excludes_null():
    sessions = pd.DataFrame({
        "has_purchase": [True, True],
        "revenue": [100.0, np.nan],
    })
    # Should sum only valid non-null revenue (100.0)
    assert total_revenue(sessions) == pytest.approx(100.0)


def test_revenue_per_purchasing_session():
    sessions = pd.DataFrame({
        "has_purchase": [True, True, False],
        "revenue": [60.0, 40.0, 0.0],
    })
    assert revenue_per_purchasing_session(sessions) == pytest.approx(50.0)


def test_stage_conversion_rates():
    sessions = pd.DataFrame({
        "has_view_item": [True, True, True, True],
        "has_add_to_cart": [True, True, False, False],
        "has_begin_checkout": [True, False, False, False],
        "has_purchase": [True, False, False, False],
    })
    rates = stage_conversion_rates(sessions)
    assert rates["total_sessions"] == 4
    assert rates["sessions_view"] == 4
    assert rates["sessions_cart"] == 2
    assert rates["sessions_checkout"] == 1
    assert rates["sessions_purchase"] == 1
    assert rates["rate_view_to_cart"] == 50.0
    assert rates["rate_cart_to_checkout"] == 50.0
    assert rates["rate_checkout_to_purchase"] == 100.0
    assert rates["rate_overall_view_to_purchase"] == 25.0


def test_daily_trends_shape(sample_events_df):
    trends = daily_trends(sample_events_df)
    assert len(trends) == 2
    assert "unique_users" in trends.columns
    assert "purchases" in trends.columns
    assert "daily_revenue" in trends.columns
    # Check 2020-11-01
    day1 = trends[trends["event_date"] == pd.Timestamp("2020-11-01")].iloc[0]
    assert day1["unique_users"] == 2
    assert day1["purchases"] == 1
    assert day1["daily_revenue"] == pytest.approx(50.0)
