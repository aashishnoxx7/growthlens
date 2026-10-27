-- =============================================================================
-- GrowthLens: 04_weekly_cohort_retention.sql
-- Purpose: Calculate weekly user retention based on first-observed-activity cohort.
-- Note: Dataset covers 2020-11-01 to 2021-01-31 (~13 weeks).
--       Recent cohorts have fewer observable follow-up weeks. Cells beyond
--       the observed period represent immature observations, NOT zero retention.
-- =============================================================================

WITH user_activity AS (
  SELECT
    user_pseudo_id,
    DATE_TRUNC(PARSE_DATE('%Y%m%d', event_date), WEEK(MONDAY)) AS activity_week
  FROM
    `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE
    _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
    AND user_pseudo_id IS NOT NULL
  GROUP BY
    user_pseudo_id,
    activity_week
),

user_cohorts AS (
  SELECT
    user_pseudo_id,
    MIN(activity_week) AS cohort_week
  FROM
    user_activity
  GROUP BY
    user_pseudo_id
),

cohort_activity AS (
  SELECT
    a.user_pseudo_id,
    c.cohort_week,
    a.activity_week,
    DATE_DIFF(a.activity_week, c.cohort_week, WEEK(MONDAY)) AS week_offset
  FROM
    user_activity a
  JOIN
    user_cohorts c ON a.user_pseudo_id = c.user_pseudo_id
),

cohort_sizes AS (
  SELECT
    cohort_week,
    COUNT(DISTINCT user_pseudo_id) AS cohort_size
  FROM
    cohort_activity
  WHERE
    week_offset = 0
  GROUP BY
    cohort_week
),

retention_counts AS (
  SELECT
    cohort_week,
    week_offset,
    COUNT(DISTINCT user_pseudo_id) AS active_users
  FROM
    cohort_activity
  GROUP BY
    cohort_week,
    week_offset
)

SELECT
  c.cohort_week,
  s.cohort_size AS week_0_users,

  -- Weekly retention percentages
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 0, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_0,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 1, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_1,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 2, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_2,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 3, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_3,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 4, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_4,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 5, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_5,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 6, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_6,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 7, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_7,
  ROUND(SAFE_DIVIDE(MAX(IF(r.week_offset = 8, r.active_users, NULL)), s.cohort_size) * 100, 1) AS pct_week_8

FROM
  cohort_sizes s
JOIN
  (SELECT DISTINCT cohort_week FROM user_cohorts) c ON s.cohort_week = c.cohort_week
LEFT JOIN
  retention_counts r ON s.cohort_week = r.cohort_week
GROUP BY
  c.cohort_week,
  s.cohort_size
ORDER BY
  c.cohort_week ASC;
