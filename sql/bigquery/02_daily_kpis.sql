-- =============================================================================
-- GrowthLens: 02_daily_kpis.sql
-- Purpose: Aggregate daily executive metrics including distinct users, sessions,
--          funnel milestone events, and total purchase revenue.
-- Grain: One row per calendar date (YYYY-MM-DD).
-- =============================================================================

WITH extracted_events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    user_pseudo_id,
    -- Extract session ID
    (
      SELECT ep.value.int_value 
      FROM UNNEST(event_params) AS ep 
      WHERE ep.key = 'ga_session_id' 
      LIMIT 1
    ) AS ga_session_id,
    event_name,
    ecommerce.purchase_revenue_in_usd AS purchase_revenue
  FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
),

sessions_flagged AS (
  SELECT
    event_date,
    user_pseudo_id,
    CONCAT(user_pseudo_id, '_', CAST(ga_session_id AS STRING)) AS session_key,
    event_name,
    purchase_revenue
  FROM
    extracted_events
  WHERE
    user_pseudo_id IS NOT NULL
    AND ga_session_id IS NOT NULL
),

daily_session_level AS (
  SELECT
    event_date,
    session_key,
    user_pseudo_id,
    LOGICAL_OR(event_name = 'view_item') AS has_view_item,
    LOGICAL_OR(event_name = 'add_to_cart') AS has_add_to_cart,
    LOGICAL_OR(event_name = 'begin_checkout') AS has_begin_checkout,
    LOGICAL_OR(event_name = 'purchase') AS has_purchase,
    SUM(IF(event_name = 'purchase', COALESCE(purchase_revenue, 0), 0)) AS session_revenue
  FROM
    sessions_flagged
  GROUP BY
    event_date,
    session_key,
    user_pseudo_id
)

SELECT
  event_date,
  COUNT(DISTINCT user_pseudo_id) AS active_users,
  COUNT(DISTINCT session_key) AS total_sessions,
  
  -- Milestone counts
  COUNTIF(has_view_item) AS sessions_with_view_item,
  COUNTIF(has_add_to_cart) AS sessions_with_add_to_cart,
  COUNTIF(has_begin_checkout) AS sessions_with_checkout,
  COUNTIF(has_purchase) AS sessions_with_purchase,

  -- Conversion rate (Sessions with purchase / Total valid sessions)
  ROUND(SAFE_DIVIDE(COUNTIF(has_purchase), COUNT(DISTINCT session_key)) * 100, 2) AS session_conversion_rate_pct,

  -- Revenue totals (summed strictly at the purchase level)
  ROUND(SUM(session_revenue), 2) AS total_revenue_usd,
  ROUND(SAFE_DIVIDE(SUM(session_revenue), COUNTIF(has_purchase)), 2) AS revenue_per_purchasing_session_usd

FROM
  daily_session_level
GROUP BY
  event_date
ORDER BY
  event_date ASC;
