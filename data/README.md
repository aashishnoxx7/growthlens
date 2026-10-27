# GrowthLens Data Directory

This directory stores analytical datasets used by GrowthLens in **Local Mode**.

## What Belongs Here

- Extracted historical sample GA4 data (`ga4_sample_events.parquet` / `.csv`)
- Generated synthetic demo data (`demo_events.parquet` / `.csv`)
- Custom event extracts formatted to the GrowthLens canonical schema

## What Must NEVER Be Committed

- Raw personal data or un-obfuscated client datasets
- Service account JSON keys or API credentials
- Large binary database dumps (files in this directory are gitignored by default)

## Canonical Event Schema

Files loaded by GrowthLens must contain at minimum:
- `event_date`: String ('YYYY-MM-DD') or Date
- `event_timestamp`: Datetime (UTC) or microsecond integer since epoch
- `event_name`: String ('session_start', 'view_item', 'add_to_cart', 'begin_checkout', 'purchase', etc.)
- `user_pseudo_id`: String (GA4 pseudonymous client ID)

Optional columns utilized in segmentation and deep analysis:
- `session_id`: GA4 session identifier
- `session_key`: `f"{user_pseudo_id}_{session_id}"`
- `device_category`: 'desktop', 'mobile', 'tablet'
- `traffic_source`: First-user traffic source (e.g. 'google', 'direct')
- `traffic_medium`: First-user medium (e.g. 'organic', 'cpc')
- `revenue`: Purchase revenue in USD
- `transaction_id`: Ecommerce transaction ID

## Generating Demo Data

To populate this folder with a deterministic synthetic dataset:
```bash
python scripts/generate_demo_data.py
```
This generates `data/demo_events.parquet` and `data/demo_events.csv` without requiring any cloud access.

## Extracting Real Public GA4 Sample Data

To extract the public GA4 ecommerce dataset from BigQuery:
```bash
python scripts/extract_bigquery.py --output data/ga4_sample_events.parquet
```
Requires Google Cloud authentication (`gcloud auth application-default login`) and a configured `GOOGLE_CLOUD_PROJECT`.
