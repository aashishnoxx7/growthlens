# Methodology — GrowthLens

This document explains the analytical methods used in GrowthLens and the assumptions underlying each calculation.

---

## 1. Data Source

**Source:** `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`

**Documented period:** November 1, 2020 – January 31, 2021

**Nature of the data:** This is a historical, obfuscated sample dataset provided by Google for educational purposes. It does NOT represent current Google property traffic, any named company's actual performance, or a real user population. User identifiers are pseudonymous and obfuscated. Revenue figures may be scaled or altered.

**Do not:**
- Describe findings from this dataset as current Google business performance.
- Use revenue figures for financial modeling without explicit scaling disclaimers.
- Assume that identified patterns apply to any real ecommerce company.

---

## 2. Session Identifier Construction

GA4's `ga_session_id` event parameter is an **integer timestamp** that uniquely identifies sessions within a user, but is **NOT globally unique**. Two different users can have the same `ga_session_id` value.

**Correct session key:**
```
session_key = CONCAT(user_pseudo_id, '_', CAST(ga_session_id AS STRING))
```

Both fields must be non-NULL for a valid session key. Events where either is NULL are excluded from session-level analysis and logged.

**Why this matters:** Using `ga_session_id` alone as a session identifier would merge sessions from different users with the same session integer, producing incorrect metrics.

---

## 3. Funnel Methodology

### Stage definition

The purchase funnel tracks these GA4 event names in order:
1. `view_item` — Product Viewed
2. `add_to_cart` — Added to Cart
3. `begin_checkout` — Checkout Started
4. `purchase` — Purchase Completed

### Temporal ordering

The funnel uses **first-occurrence timestamps** within each session. A session is counted at stage N only if:
- It reached stage N-1 (first occurrence of N-1 exists).
- The first occurrence of stage N happened **after** the first occurrence of stage N-1.

This prevents sessions with out-of-order events (e.g., a `purchase` timestamp before `view_item`) from being incorrectly counted at later stages.

### Session-based vs. user-based funnel

The primary analysis is **session-based**:
- Denominator = sessions reaching stage 1 (view_item).
- Each session counts independently.
- One user with 3 sessions counts as 3 denominator entries.

This is appropriate for identifying drop-off points within individual visits, not for understanding how many distinct individuals completed a purchase.

### What funnel analysis cannot establish

- **Cause** of drop-off: A high drop-off rate at a stage does not prove a UX defect. Traffic intent, product-market fit, pricing, and instrumentation gaps also affect funnel metrics.
- **User intent**: Sessions that leave after viewing a product may be comparison-shopping, not experiencing friction.

---

## 4. Cohort Assignment

**Method:** Users are assigned to the calendar week (Monday-to-Sunday) containing their first observed event in the selected dataset.

**Terminology:** "First-observed-activity cohort." This is explicitly NOT a registration cohort, activation cohort, or first-purchase cohort. It simply captures when a user was first seen in this dataset snapshot.

**Week numbering:** Week 0 = the user's cohort week. Week 1 = the following calendar week. A user active in week 0 contributes to week-0 retention (always). A user active in week 1 contributes to week-1 retention for their cohort.

**Immature cells:** A cohort-week cell is immature when `cohort_week + (week_offset * 7 days) > max observed date`. Immature cells are marked as `NaN`, not zero. Showing zero would falsely imply zero retention rather than insufficient data.

---

## 5. Attribution Methodology

GA4's `traffic_source.source`, `traffic_source.medium`, and `traffic_source.name` fields represent **first-user attribution** — the source that acquired the user when they first appeared in the dataset. They do NOT represent the session-level traffic source.

**Implication:** A user acquired via Google organic search may return later via direct navigation. All their sessions will show `google / organic` in first-user fields, even if the converting session was a direct visit.

**What this analysis CANNOT provide:**
- Session-level attribution.
- Last-touch attribution.
- Data-driven attribution.
- Return on ad spend (ROAS) — advertising spend data is not in this dataset.
- Customer acquisition cost (CAC) — same limitation.

---

## 6. Revenue Methodology

Revenue comes from `ecommerce.purchase_revenue_in_usd` at the event level.

**NULL treatment:** A purchase event with NULL revenue is flagged as a data-quality issue. It is excluded from revenue totals. It is NOT counted as zero, because zero and missing are meaningfully different.

**Double-counting prevention:**
- Revenue is summed at the `purchase` event level, not at the item level.
- `UNNEST(items)` is used only for item-level analysis (product performance), where revenue is sourced from `items.item_revenue`, not from `ecommerce.purchase_revenue_in_usd`.
- Joining event-level data with item-level data and then summing event revenue produces inflated totals proportional to the number of items per order.

---

## 7. Missing Data Decisions

| Field | Missing Handling | Justification |
|---|---|---|
| `user_pseudo_id` | Exclude from user/session metrics | Cannot attribute to any user |
| `session_id` | Exclude from session metrics | Cannot construct valid session key |
| `device_category` | Fill with 'unknown' | Device segmentation limited; does not prevent other analysis |
| `traffic_source` | Fill with '(none)' | Consistent with GA4 direct traffic convention |
| `revenue` (non-purchase) | Leave as NULL | Non-purchase events have no revenue |
| `revenue` (purchase) | Flag as quality issue, exclude from totals | Ambiguous — do not zero-fill without confirmation |
| `transaction_id` (purchase) | Flag as quality issue | Revenue deduplication requires transaction ID |

---

## 8. Statistical Methods (Experiment Lab)

### Hypothesis test
Two-sided two-proportion z-test using pooled proportion under H₀.

### Confidence intervals
Wilson score intervals for individual proportions. Normal approximation for the difference in proportions.

### Sample size estimation
Standard power analysis formula for two proportions:
```
n = (z_α/2 + z_β)² × (p₁(1-p₁) + p₂(1-p₂)) / δ²
```
where δ = minimum detectable effect (absolute).

### Limitations
- The z-test assumes independence of observations and large enough samples for normal approximation.
- P < α does not prove business significance. A small, practically unimportant difference can be statistically significant with large enough samples.
- A non-significant result does not prove equivalence — the test may be underpowered.

---

## 9. Observed vs. Simulated Results

| Category | Source | Labeling |
|---|---|---|
| Executive overview KPIs | GA4 obfuscated sample (or demo) | "Historical observed" |
| Funnel analysis | GA4 obfuscated sample (or demo) | "Observed in dataset" |
| Cohort retention | GA4 obfuscated sample (or demo) | "Observed in dataset" |
| Acquisition breakdown | GA4 obfuscated sample (or demo) | "Observed in dataset" |
| A/B test results | Randomly generated with user parameters | "SIMULATED — not real data" |
| Recommendations | Derived from observed metrics using rules | "Hypothesis for investigation" |

The Experiment Lab page prominently labels all results as simulated. Simulated results are never combined with observed business KPIs.
