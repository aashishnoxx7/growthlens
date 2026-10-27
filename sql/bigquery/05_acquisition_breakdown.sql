-- =============================================================================
-- GrowthLens: 05_acquisition_breakdown.sql
-- Purpose: Evaluate performance across acquisition channels (source / medium).
--
-- CRITICAL METHODOLOGY NOTE:
-- GA4's traffic_source.source / medium describe FIRST-USER acquisition,
-- NOT session-level attribution. This query analyses how users acquired through
-- these initial touchpoints perform throughout the observation period.
-- Advertising spend and CAC/ROAS are not available in this public dataset.
-- =============================================================================

WITH session_events AS (
  SELECT
    user_pseudo_id,
    CONCAT(
      user_pseudo_id, 
      '_', 
      CAST((SELECT ep.value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)
    ) AS session_key,
    COALESCE(traffic_source.source, '(direct)') AS traffic_source,
    COALESCE(traffic_source.medium, '(none)') AS traffic_medium,
    event_name,
    ecommerce.purchase_revenue_in_usd AS purchase_revenue
  FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
),

session_aggregates AS (
  SELECT
    traffic_source,
    traffic_medium,
    session_key,
    user_pseudo_id,
    LOGICAL_OR(event_name = 'view_item') AS has_view_item,
    LOGICAL_OR(event_name = 'add_to_cart') AS has_add_to_cart,
    LOGICAL_OR(event_name = 'begin_checkout') AS has_begin_checkout,
    LOGICAL_OR(event_name = 'purchase') AS has_purchase,
    SUM(IF(event_name = 'purchase', COALESCE(purchase_revenue, 0), 0)) AS revenue
  FROM
    session_events
  WHERE
    session_key IS NOT NULL 
    AND NOT ENDS_WITH(session_key, '_null')
  GROUP BY
    traffic_source,
    traffic_medium,
    session_key,
    user_pseudo_id
)

SELECT
  traffic_source,
  traffic_medium,
  COUNT(DISTINCT user_pseudo_id) AS distinct_users,
  COUNT(DISTINCT session_key) AS total_sessions,

  -- Funnel steps
  COUNTIF(has_view_item) AS sessions_with_view_item,
  COUNTIF(has_add_to_cart) AS sessions_with_add_to_cart,
  COUNTIF(has_begin_checkout) AS sessions_with_checkout,
  COUNTIF(has_purchase) AS sessions_with_purchase,

  -- Conversion rates
  ROUND(SAFE_DIVIDE(COUNTIF(has_purchase), COUNT(DISTINCT session_key)) * 100, 2) AS session_conversion_rate_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(has_purchase), COUNTIF(has_view_item)) * 100, 2) AS view_to_purchase_conversion_pct,

  -- Revenue
  ROUND(SUM(revenue), 2) AS total_revenue_usd,
  ROUND(SAFE_DIVIDE(SUM(revenue), COUNTIF(has_purchase)), 2) AS avg_revenue_per_purchasing_session_usd,

  -- Minimum sample threshold flag (< 30 sessions)
  (COUNT(DISTINCT session_key) < 30) AS is_low_sample

FROM
  session_aggregates
GROUP BY
  traffic_source,
  traffic_medium
ORDER BY
  total_sessions DESC;
