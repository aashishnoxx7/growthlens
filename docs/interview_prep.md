# Interview Preparation Guide — GrowthLens

This guide prepares you for technical and analytical interviews by covering the key decisions made in this project. Questions are specific to GrowthLens rather than generic data-interview questions.

---

## 1. Why this dataset?

**Likely question:** "Why did you choose the GA4 obfuscated ecommerce sample dataset?"

**Answer framework:**
- It is a **real, publicly available dataset** from an authoritative source (Google), not a Kaggle toy dataset.
- It uses **production GA4 schema** — nested structs, repeated fields, `event_params` arrays — which requires genuine SQL skill to navigate.
- The **ecommerce context** is directly relevant to product analytics and growth roles.
- It is **historical and bounded** (Nov 2020–Jan 2021), which forces explicit handling of data limitations rather than pretending the analysis is current.
- The **obfuscation** is a realistic constraint — interviewers can ask about how you handle imperfect, real-world data.

**Important:** Always state that the data is obfuscated, historical, and not current Google performance. This shows analytical integrity.

---

## 2. SQL design decisions

**Likely question:** "Walk me through your most complex SQL query."

**Focus on `03_session_funnel.sql`:**
- Why a CTE-based approach: readability, testability, ability to reference intermediate results.
- Why `UNNEST(event_params)` is needed: GA4 stores event parameters as a repeated struct (`ARRAY<STRUCT<key STRING, value RECORD>>`), not flat columns.
- Why `_TABLE_SUFFIX BETWEEN '20201101' AND '20210131'`: BigQuery shards GA4 data by date into wildcard tables. Explicit date bounds prevent full-table scans and cost overruns.
- Why session key = `CONCAT(user_pseudo_id, '_', ga_session_id)`: `ga_session_id` alone is not globally unique — it's a per-user integer. Without combining with `user_pseudo_id`, different users with the same session integer would be merged.
- Revenue double-counting: Never join event-level data with `UNNEST(items)` and then sum `purchase_revenue_in_usd`. The join fans out the event row to one row per item, multiplying revenue.

---

## 3. Funnel methodology

**Likely question:** "How did you handle the funnel sequencing?"

**Key points:**
- **First-occurrence rule:** For each session, find the minimum (first) timestamp of each funnel event. This avoids counting repeated events as separate funnel entries.
- **Temporal ordering:** Stage N is only counted if its first timestamp is strictly after stage N-1's first timestamp. This handles cases like out-of-order tracking fires.
- **Session-based vs. user-based:** The primary funnel is session-based. One user's three sessions contribute three denominator entries. This is appropriate for identifying within-session drop-off, not long-term user conversion.
- **What the funnel doesn't measure:** User intent, off-session comparison shopping, or whether the drop-off was caused by a UX defect vs. deliberate abandonment.

**Tricky edge case:** What happens if `add_to_cart` fires before `view_item` in a session? In this implementation, `add_to_cart` is only counted if a `view_item` precedes it. If `add_to_cart` appears alone, it doesn't count in the `add_to_cart` funnel stage.

---

## 4. Cohort retention

**Likely question:** "How did you define and calculate retention cohorts?"

**Key points:**
- **Cohort definition:** The calendar week (Monday start) of each user's first observed event. Explicitly called "first-observed-activity cohort," not a registration or first-purchase cohort.
- **Week offset:** `(event_week - cohort_week) in days / 7`, clipped at 0.
- **Week 0 ≈ 100%:** By definition, all users in a cohort were active in week 0. Deviations from 100% would indicate a bug in the cohort-assignment logic.
- **Immature cells:** If `cohort_week + N weeks > dataset_max_date`, the cell is NaN, not 0. Showing zero would imply zero retention when the data simply hasn't been observed yet.
- **Dataset limitation:** The 13-week window means that only the earliest cohorts (November 2020) have mature multi-week retention data. Avoid drawing conclusions about long-term loyalty.

---

## 5. Experimentation

**Likely question:** "How did you implement the A/B test calculator?"

**Statistical methods:**
- **Two-proportion z-test** with pooled proportion under H₀. Appropriate for comparing binary conversion rates between two groups.
- **Wilson score CI** for individual proportions — more accurate than Wald interval for small samples or extreme proportions.
- **Normal approximation CI** for the difference in proportions.
- **Power/sample size formula:** `n = (z_α/2 + z_β)² × (p₁(1-p₁) + p₂(1-p₂)) / δ²`

**Key distinctions to articulate:**
- Statistical significance ≠ commercial significance. A 0.01pp improvement can be statistically significant with millions of users but commercially irrelevant.
- A non-significant result ≠ equivalence (failure to reject H₀).
- Type I error (α): false positive — concluding an effect when none exists.
- Type II error (β = 1 − power): false negative — missing a real effect.

**Why Wilson CI over Wald:** Wald CI can produce intervals outside [0,1] for small samples. Wilson is more robust.

---

## 6. Statistical significance vs. business significance

**Likely question:** "Can you give an example where statistical significance doesn't mean business significance?"

**Framework:**
- With 1,000,000 users per arm, a 0.001pp improvement in conversion will be statistically significant (p < 0.05) but almost certainly not worth the cost of implementation.
- With 100 users per arm, a 5pp improvement may not be statistically significant (underpowered) even if real.
- Business significance requires: minimum effect size that justifies implementation cost, feasibility of maintaining the change, and downstream impacts (e.g., if improving checkout conversion also reduces average order value).

---

## 7. Missing data and quality checks

**Likely question:** "How did you handle missing revenue data?"

**Answer:**
- NULL revenue on a purchase event is a data-quality issue, not zero revenue. Treating it as zero would artificially deflate average order value and total revenue.
- Missing revenue events are excluded from revenue aggregations and counted in the Data Quality report.
- Remediation: verify `ecommerce.purchase_revenue_in_usd` is populated by the GA4 implementation.

**Duplicate events:**
- Legitimate events can share identical (user, timestamp, event_name) values (e.g., rapid page re-loads).
- Deduplication is flagged and quantified, but not automatically applied. The rule must be documented and justified for each analysis context.

---

## 8. Revenue calculation risks

**Likely question:** "What are the ways revenue could be wrong in this analysis?"

1. **NULL revenue:** Purchase events without `purchase_revenue_in_usd` silently excluded (or wrongly zeroed).
2. **Fan-out from item join:** `UNNEST(items)` creates one row per item. Summing `ecommerce.purchase_revenue_in_usd` at that level multiplies it by item count.
3. **Duplicate purchase events:** Same `transaction_id` appearing twice (e.g., retry events) double-counts revenue. Deduplication by `transaction_id` is needed for accurate totals.
4. **Currency:** The dataset uses USD. Multi-currency sources would require exchange rate handling.
5. **Obfuscation:** The dataset values may have been scaled — do not use for real financial modeling.

---

## 9. Attribution limitations

**Likely question:** "Why can't you measure ROAS or CAC from this dataset?"

- `traffic_source` fields in GA4 are **first-user attribution** — the source when the user was first seen. They don't change per session.
- There is no **advertising spend** data in this dataset. ROAS = Revenue / Spend; without spend, ROAS is incalculable.
- There is no **last-touch or data-driven attribution** — only first-touch.
- Without a link to an advertising platform (Google Ads, Meta), campaign-level spend is unavailable.
- **What you can say:** "Channel X drove N sessions with a Z% conversion rate." That's descriptive, not ROI analysis.

---

## 10. Business recommendations

**Likely question:** "How are your recommendations generated?"

- **Rule-based logic:** Each recommendation pattern is an explicit business rule (e.g., "If a funnel stage loses >30% of sessions, flag it"). No LLM is involved.
- **Traceability:** Every recommendation references its specific metric value (e.g., "add_to_cart stage dropped 52% of sessions entering that stage").
- **Minimum thresholds:** Segments with fewer than 30 sessions are flagged as low-sample rather than generating spurious recommendations.
- **Causality caveat:** All recommendations are explicitly labeled as hypotheses. The data shows associations, not causes.

---

## 11. What additional data would establish causality?

- **Session recordings** (Hotjar, FullStory) to understand what users do at drop-off points.
- **Error logs** to detect technical failures at checkout.
- **Customer surveys** to understand intent at abandonment.
- **A/B test results** from actual experiments (not simulated).
- **Advertising spend** for ROI calculation.
- **CRM data** for authenticated user stitching across devices.
- **Longer time window** for mature cohort retention analysis.
