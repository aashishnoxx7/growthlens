# Business Recommendations Report

> **Instructions:** This is a template. Populate the `[PLACEHOLDER]` values by running GrowthLens against your data and exporting results from the Recommendations page.
> 
> **Data source:** `[BigQuery GA4 Sample | Synthetic Demo | Local file: filename]`  
> **Analysis date:** `[DATE]`  
> **Date range analyzed:** `[START DATE] – [END DATE]`  
> **Total sessions analyzed:** `[N]`

---

## Executive Summary

`[Populate after running analysis — describe top 2-3 findings in 2-3 sentences]`

**Priority actions:**
1. `[Recommendation 1 — highest priority]`
2. `[Recommendation 2]`
3. `[Recommendation 3]`

---

## Finding 1: Funnel Drop-Off

**Stage with largest loss:** `[stage name]`  
**Sessions lost at this stage:** `[N] ([X]%)`  
**Overall view-to-purchase conversion:** `[X]%`

### Observation
`[Describe the specific drop-off observed in your data]`

### Hypothesis
If friction at the `[stage]` step is reduced (e.g., `[specific hypothesis]`), sessions proceeding to the next step should increase. This is an association, not a confirmed cause.

### Recommended Next Step
`[Specific action: e.g., "Conduct usability testing of the checkout form on mobile devices"]`

### How to Validate
Run an A/B test. Use the Experiment Lab to estimate required sample size. Measure step-to-step conversion rate for treatment vs. control over `[N]` business cycles.

### Limitations
Drop-off reflects observed session counts. The cause could be UX friction, traffic intent mismatch, pricing concerns, or incomplete tracking. Investigate multiple hypotheses before building.

---

## Finding 2: Device Performance Gap

**Device with lowest conversion:** `[device]`  
**Conversion rate:** `[X]%` vs overall `[Y]%`  
**Sessions from this device:** `[N]`

### Observation
`[Populate with specific numbers from device breakdown analysis]`

### Hypothesis
`[Specific hypothesis based on observed data]`

### Recommended Next Step
`[Specific action]`

### How to Validate
`[Specific measurement plan]`

### Limitations
Device-level conversion differences may reflect user intent differences (mobile browsers vs. dedicated desktop shoppers) rather than UX quality alone.

---

## Finding 3: Acquisition Channel Quality

**Channel analyzed:** `[source / medium]`  
**Sessions:** `[N]`  
**Conversion rate:** `[X]%` vs overall `[Y]%`

### Observation
`[Populate from acquisition analysis]`

### Hypothesis
`[Specific hypothesis]`

### Recommended Next Step
`[Specific action]`

### How to Validate
`[Measurement plan]`

### Limitations
This dataset uses first-user attribution, not session-level attribution. Advertising spend data is unavailable — ROAS cannot be assessed. Channel differences may reflect audience intent rather than channel quality.

---

## Data Quality Findings

`[Populate from Data Quality page export]`

**Overall data quality status:** `[pass / warn / fail]`  
**Critical issues:** `[N]`  
**Warnings:** `[N]`

### Impact on Metrics
`[List which metrics are affected by quality issues]`

---

## Appendix: Metric Definitions

See [metrics_dictionary.md](metrics_dictionary.md) for complete definitions of all KPIs referenced in this report.

---

## Disclaimer

All findings in this report are **observed associations** derived from the GA4 obfuscated sample dataset (Nov 2020–Jan 2021). They are hypotheses for further investigation, not proven causal relationships. This dataset is historical and obfuscated — findings should not be represented as current business performance or attributed to any specific company.
