# Metrics Dictionary — GrowthLens

> **Data source:** GA4 Obfuscated Sample Ecommerce Dataset  
> **Period:** November 1, 2020 – January 31, 2021  
> **Grain:** Session-level primary analysis; event-level for counts

---

## 1. Unique Users

| Attribute | Value |
|---|---|
| **Name** | Unique Users |
| **Business Definition** | Count of distinct pseudonymous user identifiers observed in the selected date range and filters |
| **Calculation** | `COUNT(DISTINCT user_pseudo_id)` |
| **Numerator** | Distinct `user_pseudo_id` values |
| **Denominator** | N/A (count metric) |
| **Required Columns** | `user_pseudo_id` |
| **Grain** | Event-level input, user-level output |
| **NULL Handling** | NULL `user_pseudo_id` events are excluded from the count and flagged by Data Quality |
| **Limitations** | `user_pseudo_id` is a pseudonymous GA4 cookie identifier, not an authenticated account. The same physical person may appear as multiple users across devices or browsers. Cookie resets and browser privacy features affect continuity. |

---

## 2. Valid Sessions

| Attribute | Value |
|---|---|
| **Name** | Valid Sessions |
| **Business Definition** | Count of distinct session keys constructed from the combination of `user_pseudo_id` and the GA4 `ga_session_id` event parameter |
| **Calculation** | `COUNT(DISTINCT session_key)` where `session_key = CONCAT(user_pseudo_id, '_', ga_session_id)` |
| **Numerator** | Distinct `session_key` values |
| **Denominator** | N/A |
| **Required Columns** | `user_pseudo_id`, `session_id` (extracted from `event_params`) |
| **Grain** | Event-level input, session-level output |
| **NULL Handling** | Sessions where either `user_pseudo_id` or `session_id` is NULL are invalid and excluded. Their count is logged. |
| **Limitations** | GA4's `ga_session_id` is an integer that resets per user, so it is **not** globally unique. A session key that combines both identifiers is required. Cross-device sessions are not stitched in this dataset. |

---

## 3. Session Conversion Rate

| Attribute | Value |
|---|---|
| **Name** | Session Conversion Rate |
| **Business Definition** | Proportion of valid sessions that contain at least one `purchase` event |
| **Calculation** | `Sessions with purchase / Total valid sessions` |
| **Numerator** | Sessions where `has_purchase = True` |
| **Denominator** | Total valid sessions |
| **Required Columns** | `session_key`, `event_name` |
| **Grain** | Session-level |
| **NULL Handling** | Returns None when denominator is zero |
| **Limitations** | This is a session-level rate, not a user-level rate. One user with 10 sessions counts as 10 denominators. Do not confuse with user conversion rate. A session with a purchase but without a preceding product view is possible (e.g., direct purchase URL) but unusual — inspect with Data Quality. |

---

## 4. Funnel Conversion Rates

> Each rate below is computed between adjacent funnel stages. Rates use the stage's own count as denominator, not the first stage.

| Stage Transition | Numerator | Denominator |
|---|---|---|
| Product Viewed → Added to Cart | Sessions with `add_to_cart` (after `view_item`) | Sessions with `view_item` |
| Added to Cart → Checkout Started | Sessions with `begin_checkout` (after `add_to_cart`) | Sessions with `add_to_cart` |
| Checkout Started → Purchase | Sessions with `purchase` (after `begin_checkout`) | Sessions with `begin_checkout` |
| Overall: View → Purchase | Sessions with `purchase` | Sessions with `view_item` |

**Ordering:** Temporal ordering is enforced. A session is counted at stage N only if the first occurrence of stage N-1 precedes the first occurrence of stage N.

**Limitations:** 
- Funnel ordering is enforced using `event_timestamp`. Events with identical microsecond timestamps are treated as simultaneous.
- Users may enter the purchase journey at any stage (e.g., direct checkout URL). The funnel captures only the portion of sessions with a product view as the entry point.

---

## 5. Purchase Revenue

| Attribute | Value |
|---|---|
| **Name** | Purchase Revenue |
| **Business Definition** | Sum of `ecommerce.purchase_revenue_in_usd` for all `purchase` events in the selected scope |
| **Calculation** | `SUM(purchase_revenue_in_usd)` over purchase events only |
| **Numerator** | Sum of revenue |
| **Denominator** | N/A |
| **Required Columns** | `revenue` (from `ecommerce.purchase_revenue_in_usd`), `event_name = 'purchase'` |
| **NULL Handling** | **NULL revenue is excluded, not counted as zero.** A purchase event with NULL revenue is flagged by the Data Quality module. It is not counted in the total. |
| **Limitations** | Revenue in the GA4 sample dataset may be obfuscated, scaled, or incomplete. It represents reported ecommerce revenue, not necessarily the final settled transaction amount. Refunds are not tracked here. Do not use this metric for financial reporting. |

> ⚠️ **Revenue double-counting risk:** Never join event-level data with item-level data (`UNNEST(items)`) and then sum `ecommerce.purchase_revenue_in_usd` at the event level. This multiplies revenue by the number of items. Revenue should always be summed at the event level; item revenue should be summed at the item level. See `07_item_performance.sql` for the correct approach.

---

## 6. Revenue per Purchasing Session

| Attribute | Value |
|---|---|
| **Name** | Revenue per Purchasing Session |
| **Business Definition** | Mean revenue across sessions that contain a purchase event with valid revenue |
| **Calculation** | `SUM(revenue) / COUNT(sessions with valid revenue)` |
| **Numerator** | Total revenue from purchasing sessions with non-NULL revenue |
| **Denominator** | Count of purchasing sessions with non-NULL revenue |
| **NULL Handling** | Purchasing sessions with NULL revenue are excluded from both numerator and denominator |
| **Limitations** | This is not average order value (AOV) in the ecommerce sense — one session may contain multiple transactions. |

---

## 7. Cohort Retention Rate

| Attribute | Value |
|---|---|
| **Name** | Week-N Retention Rate |
| **Business Definition** | Proportion of users in a cohort who had any event in week N after their cohort week |
| **Calculation** | `Active users in week N / Cohort size (week-0 users)` |
| **Cohort Definition** | Calendar week (Monday start) of the user's **first observed event** in the dataset |
| **NULL Handling** | Cells where `cohort_week + N weeks > dataset max date` are marked as `NaN` (immature), not zero |
| **Limitations** | This is "first-observed-activity cohort" not a verified registration cohort. Cookie resets, cross-device usage, and obfuscation affect accuracy. The 13-week dataset period means only early cohorts have mature long-term retention data. |

---

## Important Distinctions

| Concept | Definition |
|---|---|
| **Event count** | Number of rows in the events table |
| **User count** | Distinct `user_pseudo_id` values |
| **Session count** | Distinct `session_key` values (`user_pseudo_id` + `ga_session_id`) |
| **Transaction count** | Distinct `transaction_id` values from purchase events |
| **Item count** | Rows from `UNNEST(items)` — one per line item |
| **Session conversion** | Sessions with purchase / total sessions |
| **User conversion** | Users who purchased / total users |
| **Event conversion** | Do not use — meaningless for purchase analysis |
