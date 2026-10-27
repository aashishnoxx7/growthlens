"""
Tests for growthlens.funnel module.
Verifies temporal ordering, first-occurrence rules, session deduplication, and edge cases.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import pytest

from growthlens.funnel import compute_funnel_by_segment, compute_ordered_funnel, funnel_findings


@pytest.fixture
def hand_verified_funnel_df():
    """
    Hand-verified fixture designed to test every edge case in temporal funnel logic:
      - Session A: Complete funnel in chronological order
      - Session B: Stops at view_item
      - Session C: Cart add with NO preceding view_item
      - Session D: Out of order (purchase before view_item)
      - Session E: Repeated view_item events before cart add
      - Session F: Invalid session key (missing session ID)
      - Session G & H: Distinct users who share the same ga_session_id integer
    """
    base_time = pd.Timestamp("2020-11-01 12:00:00", tz="UTC")
    
    rows = [
        # Session A: Full sequential funnel (1 -> 2 -> 3 -> 4)
        {"session_key": "userA_sess1", "user_pseudo_id": "userA", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=10)},
        {"session_key": "userA_sess1", "user_pseudo_id": "userA", "event_name": "add_to_cart", "event_timestamp": base_time + pd.Timedelta(seconds=20)},
        {"session_key": "userA_sess1", "user_pseudo_id": "userA", "event_name": "begin_checkout", "event_timestamp": base_time + pd.Timedelta(seconds=30)},
        {"session_key": "userA_sess1", "user_pseudo_id": "userA", "event_name": "purchase", "event_timestamp": base_time + pd.Timedelta(seconds=40)},

        # Session B: View item only
        {"session_key": "userB_sess1", "user_pseudo_id": "userB", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=10)},

        # Session C: Cart add without preceding view_item
        {"session_key": "userC_sess1", "user_pseudo_id": "userC", "event_name": "add_to_cart", "event_timestamp": base_time + pd.Timedelta(seconds=10)},

        # Session D: Purchase happens BEFORE view_item (out-of-order timestamps)
        {"session_key": "userD_sess1", "user_pseudo_id": "userD", "event_name": "purchase", "event_timestamp": base_time + pd.Timedelta(seconds=5)},
        {"session_key": "userD_sess1", "user_pseudo_id": "userD", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=50)},

        # Session E: Repeated view_items before add_to_cart
        {"session_key": "userE_sess1", "user_pseudo_id": "userE", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=10)},
        {"session_key": "userE_sess1", "user_pseudo_id": "userE", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=15)},
        {"session_key": "userE_sess1", "user_pseudo_id": "userE", "event_name": "add_to_cart", "event_timestamp": base_time + pd.Timedelta(seconds=25)},

        # Session F: Invalid session key (missing ga_session_id)
        {"session_key": None, "user_pseudo_id": "userF", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=10)},

        # Session G & H: ID collision test (both have session_id = 999, but different users)
        {"session_key": "userG_999", "user_pseudo_id": "userG", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=10)},
        {"session_key": "userH_999", "user_pseudo_id": "userH", "event_name": "view_item", "event_timestamp": base_time + pd.Timedelta(seconds=10)},
    ]
    return pd.DataFrame(rows)


def test_complete_funnel_counts(hand_verified_funnel_df):
    funnel = compute_ordered_funnel(hand_verified_funnel_df)
    
    # Check that all 4 stages are returned in correct order
    stages = funnel["stage"].tolist()
    assert stages == ["view_item", "add_to_cart", "begin_checkout", "purchase"]

    # Verify counts:
    # view_item: Sessions A, B, D, E, G, H = 6 sessions (F is excluded because session_key is None)
    # add_to_cart:
    #   Session A: view @ 10s, cart @ 20s -> Valid
    #   Session B: no cart -> No
    #   Session C: cart @ 10s, no view -> Invalid
    #   Session D: no cart -> No
    #   Session E: view @ 10s, cart @ 25s -> Valid
    #   Session G, H: no cart -> No
    #   Total add_to_cart = 2 (Sessions A, E)
    # begin_checkout: Session A only = 1
    # purchase: Session A only (D had purchase before view, so it is invalid) = 1
    
    counts = dict(zip(funnel["stage"], funnel["sessions"]))
    assert counts["view_item"] == 6
    assert counts["add_to_cart"] == 2
    assert counts["begin_checkout"] == 1
    assert counts["purchase"] == 1


def test_out_of_order_session_d_disallowed(hand_verified_funnel_df):
    funnel = compute_ordered_funnel(hand_verified_funnel_df)
    # Total purchases should be exactly 1 (Session A), NOT 2 (Session D's purchase was out of order)
    assert funnel.loc[funnel["stage"] == "purchase", "sessions"].iloc[0] == 1


def test_no_preceding_view_session_c_disallowed(hand_verified_funnel_df):
    funnel = compute_ordered_funnel(hand_verified_funnel_df)
    # Session C added to cart without viewing item first; add_to_cart count must be 2 (A and E), not 3
    assert funnel.loc[funnel["stage"] == "add_to_cart", "sessions"].iloc[0] == 2


def test_repeated_events_handled_consistently(hand_verified_funnel_df):
    funnel = compute_ordered_funnel(hand_verified_funnel_df)
    # Session E viewed twice; should only be counted once in view_item and once in add_to_cart
    assert funnel.loc[funnel["stage"] == "view_item", "sessions"].iloc[0] == 6


def test_empty_dataframe_returns_clean_zero_funnel():
    empty_df = pd.DataFrame(columns=["session_key", "event_timestamp", "event_name"])
    funnel = compute_ordered_funnel(empty_df)
    assert len(funnel) == 4
    assert (funnel["sessions"] == 0).all()


def test_funnel_dropoff_math(hand_verified_funnel_df):
    funnel = compute_ordered_funnel(hand_verified_funnel_df)
    # Check drop-off calculations:
    # Stage 1: 6 sessions -> Stage 2: 2 sessions => dropoff_abs = 4, dropoff_pct = 66.67%
    row0 = funnel.iloc[0]
    assert row0["dropoff_abs"] == 4
    assert row0["dropoff_pct"] == pytest.approx(66.67, 0.01)


def test_funnel_findings_identifies_worst_dropoff(hand_verified_funnel_df):
    funnel = compute_ordered_funnel(hand_verified_funnel_df)
    findings = funnel_findings(funnel)
    assert len(findings) > 0
    drop_finding = next(f for f in findings if f["type"] == "funnel_drop")
    assert drop_finding["severity"] == "high"
    assert "Product Viewed" in drop_finding["message"]
