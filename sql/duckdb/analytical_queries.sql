-- =============================================================================
-- GrowthLens: DuckDB Analytical Queries
-- Purpose: Fast local SQL analytics executing over exported Parquet or CSV records.
-- Compatible with DuckDB CLI, Python duckdb, or embedded analytical layers.
-- =============================================================================

-- Query 1: Daily Overview KPIs
SELECT
  event_date,
  COUNT(DISTINCT user_pseudo_id) AS active_users,
  COUNT(DISTINCT session_key) AS sessions,
  COUNTIF(event_name = 'view_item') AS view_events,
  COUNTIF(event_name = 'add_to_cart') AS cart_events,
  COUNTIF(event_name = 'begin_checkout') AS checkout_events,
  COUNTIF(event_name = 'purchase') AS purchases,
  ROUND(COUNTIF(event_name = 'purchase')::DOUBLE / NULLIF(COUNT(DISTINCT session_key), 0) * 100, 2) AS session_conversion_rate_pct,
  ROUND(SUM(CASE WHEN event_name = 'purchase' THEN COALESCE(revenue, 0) ELSE 0 END), 2) AS total_revenue
FROM events
WHERE session_key IS NOT NULL AND session_key != 'nan_nan'
GROUP BY event_date
ORDER BY event_date ASC;


-- Query 2: Session-Based Sequential Funnel (Ordered)
WITH first_events AS (
  SELECT
    session_key,
    MIN(CASE WHEN event_name = 'view_item' THEN event_timestamp END) AS ts_view,
    MIN(CASE WHEN event_name = 'add_to_cart' THEN event_timestamp END) AS ts_cart,
    MIN(CASE WHEN event_name = 'begin_checkout' THEN event_timestamp END) AS ts_checkout,
    MIN(CASE WHEN event_name = 'purchase' THEN event_timestamp END) AS ts_purchase
  FROM events
  WHERE session_key IS NOT NULL AND session_key != 'nan_nan'
  GROUP BY session_key
),
ordered_funnel AS (
  SELECT
    session_key,
    ts_view IS NOT NULL AS reached_view,
    ts_view IS NOT NULL AND ts_cart IS NOT NULL AND ts_cart >= ts_view AS reached_cart,
    ts_view IS NOT NULL AND ts_cart IS NOT NULL AND ts_checkout IS NOT NULL 
      AND ts_cart >= ts_view AND ts_checkout >= ts_cart AS reached_checkout,
    ts_view IS NOT NULL AND ts_cart IS NOT NULL AND ts_checkout IS NOT NULL AND ts_purchase IS NOT NULL
      AND ts_cart >= ts_view AND ts_checkout >= ts_cart AND ts_purchase >= ts_checkout AS reached_purchase
  FROM first_events
)
SELECT
  COUNTIF(reached_view) AS stage1_product_viewed_sessions,
  COUNTIF(reached_cart) AS stage2_added_to_cart_sessions,
  COUNTIF(reached_checkout) AS stage3_checkout_started_sessions,
  COUNTIF(reached_purchase) AS stage4_purchase_completed_sessions,
  ROUND(COUNTIF(reached_purchase)::DOUBLE / NULLIF(COUNTIF(reached_view), 0) * 100, 2) AS overall_funnel_conversion_pct
FROM ordered_funnel;


-- Query 3: Acquisition Channel Performance
SELECT
  COALESCE(traffic_source, '(direct)') AS traffic_source,
  COALESCE(traffic_medium, '(none)') AS traffic_medium,
  COUNT(DISTINCT session_key) AS sessions,
  COUNT(DISTINCT user_pseudo_id) AS users,
  COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN session_key END) AS purchasing_sessions,
  ROUND(COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN session_key END)::DOUBLE / NULLIF(COUNT(DISTINCT session_key), 0) * 100, 2) AS conversion_rate_pct,
  ROUND(SUM(CASE WHEN event_name = 'purchase' THEN COALESCE(revenue, 0) ELSE 0 END), 2) AS total_revenue
FROM events
WHERE session_key IS NOT NULL AND session_key != 'nan_nan'
GROUP BY traffic_source, traffic_medium
ORDER BY sessions DESC;


-- Query 4: Device Category Breakdown
SELECT
  COALESCE(device_category, 'unknown') AS device_category,
  COUNT(DISTINCT session_key) AS total_sessions,
  COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN session_key END) AS purchasing_sessions,
  ROUND(COUNT(DISTINCT CASE WHEN event_name = 'purchase' THEN session_key END)::DOUBLE / NULLIF(COUNT(DISTINCT session_key), 0) * 100, 2) AS conversion_rate_pct,
  ROUND(SUM(CASE WHEN event_name = 'purchase' THEN COALESCE(revenue, 0) ELSE 0 END), 2) AS total_revenue
FROM events
WHERE session_key IS NOT NULL AND session_key != 'nan_nan'
GROUP BY device_category
ORDER BY total_sessions DESC;
