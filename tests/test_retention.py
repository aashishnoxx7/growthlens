"""
Tests for growthlens.retention module.
Verifies cohort week assignment, week offset arithmetic, retention matrix,
and handling of incomplete/immature observation windows.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

from growthlens.retention import assign_cohorts, build_retention_matrix, retention_summary


@pytest.fixture
def cohort_fixture_df():
    """
    3 users across 3 calendar weeks:
      - Week 1 (starting 2020-11-02): User A and User B active -> Cohort 2020-11-02
      - Week 2 (starting 2020-11-09): User A returns, User C first seen -> User C Cohort 2020-11-09
      - Week 3 (starting 2020-11-16): User A returns again, User C returns
    """
    rows = [
        # User A: active in W1, W2, W3
        {"user_pseudo_id": "userA", "event_timestamp": pd.Timestamp("2020-11-02 10:00:00", tz="UTC")},
        {"user_pseudo_id": "userA", "event_timestamp": pd.Timestamp("2020-11-04 12:00:00", tz="UTC")}, # duplicate in same week
        {"user_pseudo_id": "userA", "event_timestamp": pd.Timestamp("2020-11-10 14:00:00", tz="UTC")},
        {"user_pseudo_id": "userA", "event_timestamp": pd.Timestamp("2020-11-17 09:00:00", tz="UTC")},

        # User B: active in W1 only
        {"user_pseudo_id": "userB", "event_timestamp": pd.Timestamp("2020-11-03 11:00:00", tz="UTC")},

        # User C: first active in W2, returns in W3
        {"user_pseudo_id": "userC", "event_timestamp": pd.Timestamp("2020-11-11 16:00:00", tz="UTC")},
        {"user_pseudo_id": "userC", "event_timestamp": pd.Timestamp("2020-11-18 10:00:00", tz="UTC")},
    ]
    return pd.DataFrame(rows)


def test_assign_cohorts_assigns_first_week(cohort_fixture_df):
    df_assigned = assign_cohorts(cohort_fixture_df)
    assert "cohort_week" in df_assigned.columns
    assert "week_offset" in df_assigned.columns

    # User A cohort week should be 2020-11-02
    uA = df_assigned[df_assigned["user_pseudo_id"] == "userA"]
    assert (uA["cohort_week"] == pd.Timestamp("2020-11-02")).all()

    # User C cohort week should be 2020-11-09
    uC = df_assigned[df_assigned["user_pseudo_id"] == "userC"]
    assert (uC["cohort_week"] == pd.Timestamp("2020-11-09")).all()


def test_week_offset_calculation(cohort_fixture_df):
    df_assigned = assign_cohorts(cohort_fixture_df)
    uA = df_assigned[df_assigned["user_pseudo_id"] == "userA"].sort_values("event_timestamp")
    offsets = uA["week_offset"].tolist()
    # 2 events in W0, 1 in W1, 1 in W2
    assert offsets == [0, 0, 1, 2]


def test_retention_matrix_values(cohort_fixture_df):
    matrix = build_retention_matrix(cohort_fixture_df)
    
    # Cohort 2020-11-02: size = 2 (User A, User B)
    # Week 0: 100% (2/2)
    # Week 1: 50% (User A only / 2)
    # Week 2: 50% (User A only / 2)
    c1 = pd.Timestamp("2020-11-02")
    assert matrix.loc[c1, 0] == 100.0
    assert matrix.loc[c1, 1] == 50.0
    assert matrix.loc[c1, 2] == 50.0

    # Cohort 2020-11-09: size = 1 (User C)
    # Week 0: 100% (1/1)
    # Week 1: 100% (User C active in W3 / 1)
    c2 = pd.Timestamp("2020-11-09")
    assert matrix.loc[c2, 0] == 100.0
    assert matrix.loc[c2, 1] == 100.0


def test_immature_cells_are_nan(cohort_fixture_df):
    matrix = build_retention_matrix(cohort_fixture_df)
    # For Cohort 2020-11-09, week_offset = 2 would extend past the max date (2020-11-18)
    # So week 2 for cohort 2020-11-09 should be NaN or not present
    c2 = pd.Timestamp("2020-11-09")
    if 2 in matrix.columns:
        assert np.isnan(matrix.loc[c2, 2])


def test_empty_df_returns_empty_matrix():
    empty_df = pd.DataFrame(columns=["user_pseudo_id", "event_timestamp"])
    matrix = build_retention_matrix(empty_df)
    assert matrix.empty


def test_retention_summary_metrics(cohort_fixture_df):
    matrix = build_retention_matrix(cohort_fixture_df)
    summary = retention_summary(matrix)
    assert "avg_w0_retention" in summary
    assert summary["avg_w0_retention"] == 100.0
