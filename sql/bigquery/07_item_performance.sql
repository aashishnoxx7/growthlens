-- =============================================================================
-- GrowthLens: 07_item_performance.sql
-- Purpose: Analyze product and item-level sales performance using the UNNESTed items array.
--
-- CRITICAL ANTI-FAN-OUT WARNING:
-- In GA4, an event can have multiple rows in the repeated `items` array.
-- NEVER join event-level data with item-level data and then SUM(ecommerce.purchase_revenue_in_usd).
-- Doing so multiplies order revenue by the number of line items in that order.
--
-- Revenue at the item level must be calculated strictly from:
--   COALESCE(item.item_revenue_in_usd, item.item_revenue, 0)
-- OR by keeping item-level aggregation separate from event-level aggregation.
-- =============================================================================

WITH item_events AS (
  SELECT
    PARSE_DATE('%Y%m%d', event_date) AS event_date,
    event_timestamp,
    event_name,
    ecommerce.transaction_id,
    item.item_id,
    COALESCE(item.item_name, '(not set)') AS item_name,
    COALESCE(item.item_category, '(not set)') AS item_category,
    COALESCE(item.price_in_usd, item.price, 0) AS unit_price_usd,
    COALESCE(item.quantity, 1) AS quantity,
    COALESCE(item.item_revenue_in_usd, item.item_revenue, 0) AS line_item_revenue_usd
  FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
    UNNEST(items) AS item
  WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
    AND event_name IN ('view_item', 'add_to_cart', 'purchase')
)

SELECT
  item_id,
  item_name,
  item_category,
  
  -- Item engagement
  COUNTIF(event_name = 'view_item') AS item_view_events,
  COUNTIF(event_name = 'add_to_cart') AS item_cart_add_events,
  COUNTIF(event_name = 'purchase') AS item_purchase_occurrences,

  -- Units and revenue
  SUM(IF(event_name = 'purchase', quantity, 0)) AS total_units_sold,
  ROUND(SUM(IF(event_name = 'purchase', line_item_revenue_usd, 0)), 2) AS total_item_revenue_usd,
  ROUND(AVG(IF(event_name = 'purchase' AND unit_price_usd > 0, unit_price_usd, NULL)), 2) AS avg_selling_price_usd,

  -- Item-level cart-to-purchase conversion
  ROUND(SAFE_DIVIDE(COUNTIF(event_name = 'purchase'), COUNTIF(event_name = 'add_to_cart')) * 100, 2) AS cart_to_purchase_rate_pct

FROM
  item_events
GROUP BY
  item_id,
  item_name,
  item_category
HAVING
  total_units_sold > 0 OR item_view_events >= 50
ORDER BY
  total_item_revenue_usd DESC,
  total_units_sold DESC;
