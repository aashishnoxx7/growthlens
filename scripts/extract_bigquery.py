#!/usr/bin/env python3
"""
Command-line extraction utility to pull GA4 sample events from Google Cloud BigQuery
and persist them locally as Parquet or CSV.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from growthlens.config import DATA_DIR, GA4_END_DATE, GA4_START_DATE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("extract_bigquery")


def parse_args():
    parser = argparse.ArgumentParser(description="Extract GA4 ecommerce events from BigQuery.")
    parser.add_argument("--start-date", default=GA4_START_DATE, help="Start date (YYYYMMDD)")
    parser.add_argument("--end-date", default=GA4_END_DATE, help="End date (YYYYMMDD)")
    parser.add_argument(
        "--output",
        default=str(DATA_DIR / "ga4_sample_events.parquet"),
        help="Target output file path (.parquet or .csv)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        from growthlens.bigquery_client import fetch_events_from_bq
    except ImportError as e:
        logger.error(
            "Google Cloud BigQuery dependencies not installed. "
            "Run: pip install google-cloud-bigquery google-cloud-bigquery-storage"
        )
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initiating BigQuery extraction: %s to %s", args.start_date, args.end_date)
    try:
        df = fetch_events_from_bq(start_date=args.start_date, end_date=args.end_date)
        logger.info("Extraction complete: %d records received.", len(df))

        if output_path.suffix.lower() == ".parquet":
            df.to_parquet(output_path, index=False)
        else:
            df.to_csv(output_path, index=False)

        logger.info("Saved analytical events to %s", output_path)

    except Exception as exc:
        logger.error("BigQuery extraction failed: %s", exc)
        logger.error(
            "\nTroubleshooting Guide:\n"
            "1. Authenticate with GCP: `gcloud auth application-default login`\n"
            "2. Ensure GOOGLE_CLOUD_PROJECT is set in .env with a billing-enabled project\n"
            "3. If query cost exceeds limits, widen BQ_MAX_BYTES_BILLED or narrow date range."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
