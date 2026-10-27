-- =============================================================================
-- GrowthLens: 06_device_breakdown.sql
-- Purpose: Compare user engagement, funnel progression, and conversion rates
--          across device categories (mobile, desktop, tablet).
-- =============================================================================

WITH session_events AS (
  SELECT
    user_pseudo_id,
    CONCAT(
      user_pseudo_id, 
      '_', 
      CAST((SELECT ep.value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)
    ) AS session_key,
    COALESCE(device.category, 'unknown') AS device_category,
    event_name,
    ecommerce.purchase_revenue_in_usd AS purchase_revenue
  FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
),

session_aggregates AS (
  SELECT
    device_category,
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
    device_category,
    session_key,
    user_pseudo_id
)

SELECT
  device_category,
  COUNT(DISTINCT user_pseudo_id) AS distinct_users,
  COUNT(DISTINCT session_key) AS total_sessions,

  -- Funnel steps
  COUNTIF(has_view_item) AS sessions_with_view_item,
  COUNTIF(has_add_to_cart) AS sessions_with_add_to_cart,
  COUNTIF(has_begin_checkout) AS sessions_with_checkout,
  COUNTIF(has_purchase) AS sessions_with_purchase,

  -- Step-by-step conversion rates
  ROUND(SAFE_DIVIDE(COUNTIF(has_add_to_cart), COUNTIF(has_view_item)) * 100, 2) AS view_to_cart_rate_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(has_begin_checkout), COUNTIF(has_add_to_cart)) * 100, 2) AS cart_to_checkout_rate_pct,
  ROUND(SAFE_DIVIDE(COUNTIF(has_purchase), COUNTIF(has_begin_checkout)) * 100, 2) AS checkout_to_purchase_rate_pct,

  -- Overall conversion rate
  ROUND(SAFE_DIVIDE(COUNTIF(has_purchase), COUNT(DISTINCT session_key)) * 100, 2) AS session_conversion_rate_pct,

  -- Revenue
  ROUND(SUM(revenue), 2) AS total_revenue_usd,
  ROUND(SAFE_DIVIDE(SUM(revenue), COUNTIF(has_purchase)), 2) AS avg_revenue_per_purchasing_session_usd

FROM
  session_aggregates
GROUP BY
  device_category
ORDER BY
  total_sessions DESC;
