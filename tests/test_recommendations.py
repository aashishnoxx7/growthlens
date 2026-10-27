"""
Tests for growthlens.acquisition and growthlens.recommendations modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import pytest

from growthlens.acquisition import acquisition_findings, acquisition_performance, device_performance
from growthlens.recommendations import generate_recommendations


@pytest.fixture
def session_fixture():
    return pd.DataFrame([
        {
            "session_key": f"s_{i}",
            "user_pseudo_id": f"u_{i}",
            "device_category": "mobile" if i < 30 else "desktop",
            "traffic_source": "google" if i < 25 else "facebook",
            "traffic_medium": "organic" if i < 25 else "cpc",
            "has_view_item": True,
            "has_add_to_cart": i % 2 == 0,
            "has_begin_checkout": i % 4 == 0,
            "has_purchase": i % 5 == 0,
            "revenue": 50.0 if i % 5 == 0 else 0.0,
        }
        for i in range(50)
    ])


def test_acquisition_performance_matrix(session_fixture):
    acq_df = acquisition_performance(session_fixture)
    assert not acq_df.empty
    assert "traffic_source" in acq_df.columns
    assert "traffic_medium" in acq_df.columns
    assert "conversion_rate_pct" in acq_df.columns
    assert "sessions" in acq_df.columns
    assert acq_df["sessions"].sum() == 50


def test_device_performance(session_fixture):
    dev_df = device_performance(session_fixture)
    assert not dev_df.empty
    assert set(dev_df["device_category"]) == {"mobile", "desktop"}
    assert "conversion_rate_pct" in dev_df.columns


def test_acquisition_findings(session_fixture):
    acq_df = acquisition_performance(session_fixture)
    # Overall conversion rate in fixture is 10/50 = 20%
    findings = acquisition_findings(acq_df, overall_rate=0.20)
    assert isinstance(findings, list)


def test_generate_recommendations_generates_actionable_list(session_fixture):
    dev_df = device_performance(session_fixture)
    acq_df = acquisition_performance(session_fixture)
    
    funnel_findings = [
        {
            "type": "funnel_drop",
            "severity": "high",
            "message": "Large drop-off after view_item",
            "evidence": {
                "stage": "view_item",
                "dropoff_abs": 25,
                "dropoff_pct": 50.0,
            },
        }
    ]

    quality_checks = [
        {
            "check_name": "missing_user_pseudo_id",
            "severity": "error",
            "status": "fail",
            "affected_rows": 10,
            "pct_affected": 2.0,
            "message": "10 rows missing user_pseudo_id",
            "remediation": "Check instrumentation",
        }
    ]

    recs = generate_recommendations(
        funnel_findings=funnel_findings,
        acquisition_df=acq_df,
        device_df=dev_df,
        quality_checks=quality_checks,
        overall_conversion=0.20,
    )

    assert len(recs) >= 2
    # Check required fields
    for r in recs:
        assert "priority" in r
        assert "category" in r
        assert "problem" in r
        assert "evidence" in r
        assert "recommended_action" in r
        assert "expected_direction" in r
        assert "how_to_test" in r
        assert "limitations" in r


def test_generate_recommendations_empty_inputs():
    recs = generate_recommendations()
    assert recs == []
