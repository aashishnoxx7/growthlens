-- =============================================================================
-- GrowthLens: 03_session_funnel.sql
-- Purpose: Calculate a session-based, temporally ordered conversion funnel.
-- Stages:
--   1. view_item        (Product Viewed)
--   2. add_to_cart      (Added to Cart)
--   3. begin_checkout   (Checkout Started)
--   4. purchase         (Purchase Completed)
--
-- Logic: A session is counted at stage N ONLY if:
--   a) It reached stage N-1, and
--   b) The earliest timestamp of stage N >= the earliest timestamp of stage N-1.
-- =============================================================================

WITH raw_funnel_events AS (
  SELECT
    user_pseudo_id,
    CONCAT(
      user_pseudo_id, 
      '_', 
      CAST((SELECT ep.value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS STRING)
    ) AS session_key,
    event_name,
    event_timestamp
  FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
    AND event_name IN ('view_item', 'add_to_cart', 'begin_checkout', 'purchase')
),

-- Find first timestamp of each event within each valid session
first_stage_timestamps AS (
  SELECT
    session_key,
    MIN(IF(event_name = 'view_item', event_timestamp, NULL)) AS ts_view_item,
    MIN(IF(event_name = 'add_to_cart', event_timestamp, NULL)) AS ts_add_to_cart,
    MIN(IF(event_name = 'begin_checkout', event_timestamp, NULL)) AS ts_begin_checkout,
    MIN(IF(event_name = 'purchase', event_timestamp, NULL)) AS ts_purchase
  FROM
    raw_funnel_events
  WHERE
    session_key IS NOT NULL 
    AND NOT ENDS_WITH(session_key, '_null')
  GROUP BY
    session_key
),

-- Enforce sequential temporal order
ordered_funnel_sessions AS (
  SELECT
    session_key,
    -- Stage 1: Product View
    (ts_view_item IS NOT NULL) AS reached_view_item,

    -- Stage 2: Cart Add (Must view item first and cart add timestamp >= view timestamp)
    (ts_view_item IS NOT NULL 
     AND ts_add_to_cart IS NOT NULL 
     AND ts_add_to_cart >= ts_view_item) AS reached_add_to_cart,

    -- Stage 3: Checkout (Must cart add first and checkout timestamp >= cart add timestamp)
    (ts_view_item IS NOT NULL 
     AND ts_add_to_cart IS NOT NULL 
     AND ts_begin_checkout IS NOT NULL 
     AND ts_add_to_cart >= ts_view_item
     AND ts_begin_checkout >= ts_add_to_cart) AS reached_begin_checkout,

    -- Stage 4: Purchase (Must checkout first and purchase timestamp >= checkout timestamp)
    (ts_view_item IS NOT NULL 
     AND ts_add_to_cart IS NOT NULL 
     AND ts_begin_checkout IS NOT NULL 
     AND ts_purchase IS NOT NULL
     AND ts_add_to_cart >= ts_view_item
     AND ts_begin_checkout >= ts_add_to_cart
     AND ts_purchase >= ts_begin_checkout) AS reached_purchase
  FROM
    first_stage_timestamps
),

funnel_counts AS (
  SELECT
    COUNTIF(reached_view_item) AS step1_views,
    COUNTIF(reached_add_to_cart) AS step2_carts,
    COUNTIF(reached_begin_checkout) AS step3_checkouts,
    COUNTIF(reached_purchase) AS step4_purchases
  FROM
    ordered_funnel_sessions
)

SELECT
  stage_order,
  stage_name,
  sessions,
  
  -- % of funnel entrants (Product Views)
  ROUND(SAFE_DIVIDE(sessions, FIRST_VALUE(sessions) OVER (ORDER BY stage_order ASC)) * 100, 2) AS pct_of_entrants,
  
  -- Step-to-step conversion rate (% of prior stage)
  ROUND(SAFE_DIVIDE(sessions, LAG(sessions) OVER (ORDER BY stage_order ASC)) * 100, 2) AS step_to_step_conversion_pct,

  -- Drop-off counts and percentages
  LAG(sessions) OVER (ORDER BY stage_order ASC) - sessions AS dropoff_from_prior_stage,
  ROUND(SAFE_DIVIDE(LAG(sessions) OVER (ORDER BY stage_order ASC) - sessions, LAG(sessions) OVER (ORDER BY stage_order ASC)) * 100, 2) AS dropoff_pct

FROM (
  SELECT 1 AS stage_order, '1. Product Viewed (view_item)' AS stage_name, step1_views AS sessions FROM funnel_counts
  UNION ALL
  SELECT 2 AS stage_order, '2. Added to Cart (add_to_cart)' AS stage_name, step2_carts AS sessions FROM funnel_counts
  UNION ALL
  SELECT 3 AS stage_order, '3. Checkout Started (begin_checkout)' AS stage_name, step3_checkouts AS sessions FROM funnel_counts
  UNION ALL
  SELECT 4 AS stage_order, '4. Purchase Completed (purchase)' AS stage_name, step4_purchases AS sessions FROM funnel_counts
)
ORDER BY
  stage_order ASC;
