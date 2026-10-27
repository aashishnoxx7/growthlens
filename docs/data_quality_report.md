# Data Quality Report Template

> **Instructions:** Export the actual quality report from the Data Quality page in GrowthLens.  
> **Data source:** `[BigQuery | Demo | Local]`  
> **Generated:** `[DATE]`  
> **Records analyzed:** `[N]`

---

## Overall Quality Score

**Status:** `[PASS | WARN | FAIL]`

| Category | Count |
|---|---|
| Total checks | `[N]` |
| Errors | `[N]` |
| Warnings | `[N]` |
| Passed | `[N]` |

---

## Check Results

| Check | Severity | Status | Affected Rows | % Affected | Summary |
|---|---|---|---|---|---|
| missing_user_pseudo_id | ERROR | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| missing_event_date | ERROR | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| invalid_timestamp | ERROR | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| missing_session_id | WARNING | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| invalid_session_key | WARNING | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| duplicate_events | WARNING | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| missing_device | INFO | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| unexpected_event_names | INFO | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| purchase_revenue | ERROR/INFO | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| missing_transaction_id | WARNING | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| revenue_outliers | WARNING | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |
| temporal_sequence | WARNING | `[pass/warn/fail]` | `[N]` | `[X]%` | `[message]` |

---

## Remediation Actions

`[Populate from Data Quality page — list issues and recommended fixes]`

---

## Impact on Metrics

| Quality Issue | Affected Metric | Impact |
|---|---|---|
| NULL user_pseudo_id | Unique Users, Session Count | Undercount |
| NULL revenue (purchase) | Total Revenue, Revenue/Session | Undercount |
| Missing session_id | Valid Sessions, Funnel | Undercount |
| Duplicate events | Event Counts | Overcount (if not deduplicated) |
