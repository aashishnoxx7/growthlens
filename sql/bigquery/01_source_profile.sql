-- =============================================================================
-- GrowthLens: 01_source_profile.sql
-- Dataset: bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*
-- Purpose: Profile raw source table structure, date distribution, user counts,
--          key event frequencies, and check for missing essential parameters.
-- Date Range: Documented sample period 2020-11-01 to 2021-01-31.
--
-- Cost Note: Uses bounded wildcard _TABLE_SUFFIX to scan only the sample partition range.
-- =============================================================================

WITH base_events AS (
  SELECT
    _TABLE_SUFFIX AS table_suffix,
    PARSE_DATE('%Y%m%d', event_date) AS parsed_date,
    event_timestamp,
    event_name,
    user_pseudo_id,
    device.category AS device_category,
    traffic_source.source AS traffic_source,
    traffic_source.medium AS traffic_medium,
    ecommerce.purchase_revenue_in_usd AS purchase_revenue,
    ecommerce.transaction_id AS transaction_id,
    -- Extract GA4 session ID from repeated key-value pairs
    (
      SELECT ep.value.int_value 
      FROM UNNEST(event_params) AS ep 
      WHERE ep.key = 'ga_session_id' 
      LIMIT 1
    ) AS ga_session_id
  FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
)

SELECT
  -- Time window
  MIN(parsed_date) AS min_event_date,
  MAX(parsed_date) AS max_event_date,
  COUNT(DISTINCT parsed_date) AS observed_days_count,

  -- Volume totals
  COUNT(1) AS total_events,
  COUNT(DISTINCT user_pseudo_id) AS distinct_users,
  COUNT(DISTINCT CONCAT(user_pseudo_id, '_', CAST(ga_session_id AS STRING))) AS valid_sessions,

  -- Event name distribution (Core purchase journey events)
  COUNTIF(event_name = 'session_start') AS session_start_events,
  COUNTIF(event_name = 'page_view') AS page_view_events,
  COUNTIF(event_name = 'view_item') AS view_item_events,
  COUNTIF(event_name = 'add_to_cart') AS add_to_cart_events,
  COUNTIF(event_name = 'begin_checkout') AS begin_checkout_events,
  COUNTIF(event_name = 'purchase') AS purchase_events,

  -- Data completeness indicators
  COUNTIF(user_pseudo_id IS NULL) AS null_user_ids,
  COUNTIF(ga_session_id IS NULL) AS events_missing_session_id,
  SAFE_DIVIDE(COUNTIF(ga_session_id IS NULL), COUNT(1)) * 100 AS pct_events_missing_session_id,

  -- Ecommerce purchase revenue integrity
  COUNTIF(event_name = 'purchase' AND purchase_revenue IS NULL) AS purchases_missing_revenue,
  COUNTIF(event_name = 'purchase' AND transaction_id IS NULL) AS purchases_missing_transaction_id,
  ROUND(SUM(IF(event_name = 'purchase', purchase_revenue, 0)), 2) AS total_sample_revenue_usd,
  ROUND(AVG(IF(event_name = 'purchase', purchase_revenue, NULL)), 2) AS avg_purchase_revenue_usd,
  ROUND(MAX(IF(event_name = 'purchase', purchase_revenue, NULL)), 2) AS max_single_transaction_usd

FROM base_events;
