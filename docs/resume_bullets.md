# Resume Bullets — GrowthLens Portfolio Project

> ⚠️ **Instructions:** Replace all `[bracketed placeholders]` with your actual measured results after running the analysis against real data. Do not submit these templates with placeholders intact. Never claim simulated experiment results as real business outcomes.

---

## Resume Bullet Templates

### Bullet 1 — Engineering and Scale Focus

**Template:**
> Built **GrowthLens**, an end-to-end product analytics platform processing [X]M+ GA4 events from Google's public ecommerce dataset; engineered [N] BigQuery Standard SQL queries with CTEs, window functions, UNNEST, and date-bounded wildcard-table filters, and implemented [N] automated data-quality checks covering null identifiers, revenue anomalies, and funnel-sequence violations.

**Placeholders to fill:**
- `[X]M+` — actual event count from the dataset (e.g., "2M+")
- `[N]` BigQuery queries — count of `.sql` files (currently 7)
- `[N]` quality checks — count of checks implemented (currently 12)

**ATS keywords:** Python, BigQuery, SQL, data pipeline, GA4, data quality, pandas, DuckDB, ETL

---

### Bullet 2 — Analytics and Insights Focus

**Template:**
> Delivered a session-based conversion funnel, weekly cohort-retention heatmap, and acquisition-channel analysis across [X] sessions and [Y] user cohorts; identified the largest funnel drop-off at the [STAGE] stage ([Z]% session loss) and surfaced [N] data-driven recommendations from [M] automated business-rule checks, each traceable to a documented metric definition.

**Placeholders to fill:**
- `[X]` — session count (run the app in demo or BigQuery mode and read the Valid Sessions KPI)
- `[Y]` — number of cohort weeks observed
- `[STAGE]` — actual largest drop-off stage from funnel analysis
- `[Z]%` — actual drop-off percentage
- `[N]` — number of recommendations generated from the data
- `[M]` — count of recommendation rule types (currently 4 patterns)

**ATS keywords:** cohort analysis, funnel analysis, conversion rate, retention, acquisition, data visualization, Plotly, Streamlit

---

### Bullet 3 — Statistical and Experimentation Focus

**Template:**
> Implemented an A/B-test simulation engine supporting two-proportion z-tests, Wilson score confidence intervals, and standard power/sample-size estimation; documented statistical assumptions, type I/II error trade-offs, and the distinction between statistical and commercial significance; validated calculations against [N] known reference cases using pytest.

**Placeholders to fill:**
- `[N]` known reference cases — count of experimentation tests written (check tests/test_experimentation.py)

**ATS keywords:** A/B testing, hypothesis testing, statistical significance, sample size, confidence intervals, scipy, statsmodels, pytest

---

## Important Caveats

- The GA4 dataset is obfuscated historical data. Do not claim specific revenue figures, user counts, or conversion improvements as verified real-world outcomes unless you have confirmed they represent a genuine business result.
- Simulated A/B-test results from the Experiment Lab are generated from random numbers. They must not appear in resume bullets as real experiment outcomes.
- First populate the placeholders by running the application against real data (BigQuery mode) or documenting the synthetic demo results with an explicit "demo" qualifier.

---

## Example (Demo Mode — Clearly Labeled)

> Built GrowthLens, processing 28,000+ synthetic GA4-style events in demo mode; implemented 7 BigQuery Standard SQL queries with window functions and UNNEST, 12 automated data-quality checks, and a session-based funnel revealing a 55% drop-off at the add-to-cart stage across 5,000 simulated sessions.

*(This example uses the synthetic demo. Label it clearly if using in a portfolio.)*
