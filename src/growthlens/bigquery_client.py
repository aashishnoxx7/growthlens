"""
BigQuery client for GrowthLens.

Wraps the google-cloud-bigquery SDK to:
  - Authenticate via Application Default Credentials (no hardcoded secrets).
  - Enforce cost guardrails via maximum bytes billed.
  - Run a dry-run before executing real queries.
  - Return canonical events DataFrames.

When credentials are unavailable this module raises ImportError or
google.api_core.exceptions.GoogleAPIError — the caller (data_loader.py)
handles those and falls back to demo mode.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import pandas as pd

from growthlens.config import (
    BQ_MAX_BYTES_BILLED,
    GA4_END_DATE,
    GA4_START_DATE,
    GCP_PROJECT,
)

logger = logging.getLogger(__name__)


def _get_client():
    """Return an authenticated BigQuery client or raise on failure."""
    from google.cloud import bigquery  # noqa: PLC0415

    project = GCP_PROJECT or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise EnvironmentError(
            "GOOGLE_CLOUD_PROJECT environment variable is not set. "
            "Set it to your GCP project ID (billing must be enabled)."
        )
    return bigquery.Client(project=project)


def estimate_query_bytes(query: str) -> int:
    """
    Perform a BigQuery dry-run and return the estimated bytes processed.
    Raises google.api_core.exceptions.GoogleAPIError on auth failure.
    """
    from google.cloud import bigquery  # noqa: PLC0415

    client = _get_client()
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = client.query(query, job_config=job_config)
    bytes_est = job.total_bytes_processed
    gb = bytes_est / 1e9
    logger.info("Dry-run estimate: %.2f GB (%d bytes).", gb, bytes_est)
    return bytes_est


def fetch_events_from_bq(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Execute the GA4 events extraction query against BigQuery.

    Parameters
    ----------
    start_date : YYYYMMDD string (default: GA4_START_DATE)
    end_date   : YYYYMMDD string (default: GA4_END_DATE)

    Returns
    -------
    pd.DataFrame with canonical GrowthLens columns.

    Cost safeguards
    ---------------
    - Dry-run first to estimate bytes.
    - Abort if estimate > BQ_MAX_BYTES_BILLED.
    - Set maximum_bytes_billed on the real query job.
    """
    from google.cloud import bigquery  # noqa: PLC0415

    sd = start_date or GA4_START_DATE
    ed = end_date or GA4_END_DATE

    query = _build_extraction_query(sd, ed)

    # ── Dry run ───────────────────────────────────────────────────────────────
    est_bytes = estimate_query_bytes(query)
    if est_bytes > BQ_MAX_BYTES_BILLED:
        gb_est = est_bytes / 1e9
        gb_limit = BQ_MAX_BYTES_BILLED / 1e9
        raise RuntimeError(
            f"Estimated query cost ({gb_est:.2f} GB) exceeds the configured "
            f"limit of {gb_limit:.2f} GB. Narrow the date range or increase "
            f"BQ_MAX_BYTES_BILLED in your .env file."
        )

    # ── Execute ───────────────────────────────────────────────────────────────
    client = _get_client()
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=BQ_MAX_BYTES_BILLED,
    )
    logger.info("Executing BigQuery extraction query for %s → %s.", sd, ed)
    df = client.query(query, job_config=job_config).to_dataframe()
    logger.info("BigQuery returned %d rows.", len(df))
    return df


def _build_extraction_query(start_date: str, end_date: str) -> str:
    """
    Build the parameterized GA4 extraction SQL.

    Uses _TABLE_SUFFIX date bounds to avoid scanning unnecessary partitions.
    Only the required columns are selected to minimize data transfer.
    """
    return f"""
-- GrowthLens: GA4 event extraction
-- Source: bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*
-- Period: {start_date} – {end_date}
-- Historical, obfuscated sample data — not live Google traffic.

WITH raw_events AS (
  SELECT
    event_date,
    event_timestamp,
    event_name,
    user_pseudo_id,

    -- Extract GA4 session_id from event_params (repeated struct)
    (SELECT ep.value.int_value
     FROM UNNEST(event_params) AS ep
     WHERE ep.key = 'ga_session_id'
     LIMIT 1) AS session_id,

    -- Device
    device.category          AS device_category,

    -- First-user acquisition (not session-level attribution)
    traffic_source.source    AS traffic_source,
    traffic_source.medium    AS traffic_medium,
    traffic_source.name      AS traffic_campaign,

    -- Revenue (USD); NULL for non-purchase events
    ecommerce.purchase_revenue_in_usd AS revenue,
    ecommerce.transaction_id          AS transaction_id,

    -- Page location
    (SELECT ep.value.string_value
     FROM UNNEST(event_params) AS ep
     WHERE ep.key = 'page_location'
     LIMIT 1) AS page_location

  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '{start_date}' AND '{end_date}'
    AND event_name IN (
      'session_start', 'page_view',
      'view_item', 'add_to_cart',
      'begin_checkout', 'purchase'
    )
)

SELECT
  event_date,
  event_timestamp,
  event_name,
  user_pseudo_id,
  CAST(session_id AS STRING)               AS session_id,
  CONCAT(user_pseudo_id, '_',
         CAST(COALESCE(session_id, -1) AS STRING)) AS session_key,
  COALESCE(device_category, 'unknown')     AS device_category,
  COALESCE(traffic_source, '(none)')       AS traffic_source,
  COALESCE(traffic_medium, '(none)')       AS traffic_medium,
  COALESCE(traffic_campaign, '(not set)')  AS traffic_campaign,
  SAFE_CAST(revenue AS FLOAT64)            AS revenue,
  transaction_id,
  page_location

FROM raw_events
ORDER BY user_pseudo_id, event_timestamp
"""
