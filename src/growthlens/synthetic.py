"""
Synthetic demonstration-data generator for GrowthLens.

Produces a deterministic, reproducible DataFrame that mimics the shape of
GA4 ecommerce events WITHOUT being derived from any real user behaviour.

The interface must display:
  DEMO MODE — SYNTHETIC DATA, NOT ACTUAL BUSINESS PERFORMANCE
whenever this data is active.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from growthlens.config import (
    DEMO_N_SESSIONS,
    DEMO_N_USERS,
    DEMO_RANDOM_SEED,
    FUNNEL_STAGES,
)

logger = logging.getLogger(__name__)

# ── Synthetic distribution parameters ────────────────────────────────────────
_START_DATE = datetime(2020, 11, 1, tzinfo=timezone.utc)
_END_DATE = datetime(2021, 1, 31, tzinfo=timezone.utc)
_DATE_RANGE_DAYS = (_END_DATE - _START_DATE).days

_DEVICES = ["mobile", "desktop", "tablet"]
_DEVICE_WEIGHTS = [0.52, 0.40, 0.08]

_SOURCES = ["google", "direct", "(none)", "facebook", "email", "bing"]
_SOURCE_WEIGHTS = [0.38, 0.28, 0.14, 0.10, 0.06, 0.04]

_MEDIUMS = {
    "google":   "organic",
    "direct":   "(none)",
    "(none)":   "(none)",
    "facebook": "cpc",
    "email":    "email",
    "bing":     "cpc",
}

# Funnel drop-off rates (probability of proceeding to next stage)
_FUNNEL_PROBS = {
    "session_start":   1.00,
    "page_view":       0.95,
    "view_item":       0.60,
    "add_to_cart":     0.45,
    "begin_checkout":  0.70,
    "purchase":        0.80,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _random_ts(rng: np.random.Generator, start: datetime, end: datetime) -> datetime:
    offset_s = rng.integers(0, int((end - start).total_seconds()))
    return start + timedelta(seconds=int(offset_s))


def _make_session_events(
    rng: np.random.Generator,
    user_id: str,
    session_id: str,
    session_key: str,
    device: str,
    source: str,
    medium: str,
    session_start_ts: datetime,
) -> list[dict]:
    """
    Generate a realistic sequence of events for one session.
    Returns a list of event dicts.
    """
    events: list[dict] = []
    ts = session_start_ts

    def _add(name: str, extra: dict | None = None) -> None:
        nonlocal ts
        ts = ts + timedelta(seconds=int(rng.integers(5, 120)))
        row: dict = {
            "event_date":       ts.strftime("%Y-%m-%d"),
            "event_timestamp":  ts,
            "event_name":       name,
            "user_pseudo_id":   user_id,
            "session_id":       session_id,
            "session_key":      session_key,
            "device_category":  device,
            "traffic_source":   source,
            "traffic_medium":   medium,
            "traffic_campaign": "(not set)",
            "revenue":          None,
            "transaction_id":   None,
            "page_location":    f"/page/{rng.integers(1, 50)}",
        }
        if extra:
            row.update(extra)
        events.append(row)

    # Always has session_start and at least one page_view
    _add("session_start")
    _add("page_view")

    # Probabilistic funnel progression
    if rng.random() < _FUNNEL_PROBS["view_item"]:
        _add("view_item")
        if rng.random() < _FUNNEL_PROBS["add_to_cart"]:
            _add("add_to_cart")
            if rng.random() < _FUNNEL_PROBS["begin_checkout"]:
                _add("begin_checkout")
                if rng.random() < _FUNNEL_PROBS["purchase"]:
                    rev = float(round(rng.uniform(15.0, 350.0), 2))
                    tid = f"T{rng.integers(100_000, 999_999)}"
                    _add("purchase", {"revenue": rev, "transaction_id": tid})

    # Occasional extra page views
    extra_pv = int(rng.integers(0, 4))
    for _ in range(extra_pv):
        _add("page_view")

    return events


# ── Public API ────────────────────────────────────────────────────────────────

def generate_demo_events(
    n_users: int = DEMO_N_USERS,
    n_sessions: int = DEMO_N_SESSIONS,
    seed: int = DEMO_RANDOM_SEED,
) -> pd.DataFrame:
    """
    Generate a deterministic synthetic GA4-style events DataFrame.

    Parameters
    ----------
    n_users:    Number of synthetic pseudonymous user identifiers.
    n_sessions: Total number of sessions to simulate.
    seed:       Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame with canonical GrowthLens event columns.

    Notes
    -----
    This data is ENTIRELY SYNTHETIC. It does not represent any real user
    behaviour, business performance, or Google property traffic.
    """
    logger.info("Generating synthetic demo data: %d users, %d sessions, seed=%d",
                n_users, n_sessions, seed)

    rng = np.random.default_rng(seed)

    # Pre-generate user pool
    users = [f"demo_user_{i:06d}" for i in range(n_users)]

    all_events: list[dict] = []

    for s_idx in range(n_sessions):
        user_id = users[rng.integers(0, n_users)]
        session_id = f"sess_{s_idx:07d}"
        session_key = f"{user_id}_{session_id}"

        device = rng.choice(_DEVICES, p=_DEVICE_WEIGHTS)
        source = rng.choice(_SOURCES, p=_SOURCE_WEIGHTS)
        medium = _MEDIUMS[source]

        # Distribute sessions across date range with slight weekly seasonality
        day_offset = int(rng.integers(0, _DATE_RANGE_DAYS))
        session_start = _START_DATE + timedelta(days=day_offset)

        session_events = _make_session_events(
            rng=rng,
            user_id=user_id,
            session_id=session_id,
            session_key=session_key,
            device=device,
            source=source,
            medium=medium,
            session_start_ts=session_start,
        )
        all_events.extend(session_events)

    df = pd.DataFrame(all_events)

    # ── Type coercions ────────────────────────────────────────────────────────
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], utc=True)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
    df = df.sort_values(["user_pseudo_id", "event_timestamp"]).reset_index(drop=True)

    logger.info("Synthetic demo data generated: %d events.", len(df))
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = generate_demo_events()
    print(df.head())
    print(df["event_name"].value_counts())
    print(f"Total events: {len(df):,}")
    print(f"Unique users: {df['user_pseudo_id'].nunique():,}")
    print(f"Unique sessions: {df['session_key'].nunique():,}")
