#!/usr/bin/env python3
"""
Generate and save deterministic synthetic demo data for GrowthLens.
Outputs CSV and Parquet files to the data/ directory.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from growthlens.config import DATA_DIR, DEMO_RANDOM_SEED
from growthlens.synthetic import generate_demo_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_demo_data")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Generating synthetic events dataset with seed=%d...", DEMO_RANDOM_SEED)
    df = generate_demo_events(seed=DEMO_RANDOM_SEED)

    csv_path = DATA_DIR / "demo_events.csv"
    parquet_path = DATA_DIR / "demo_events.parquet"

    logger.info("Writing CSV to %s...", csv_path)
    df.to_csv(csv_path, index=False)

    logger.info("Writing Parquet to %s...", parquet_path)
    df.to_parquet(parquet_path, index=False)

    logger.info("Successfully generated %d events:", len(df))
    logger.info("  - Unique users: %d", df["user_pseudo_id"].nunique())
    logger.info("  - Unique sessions: %d", df["session_key"].nunique())
    logger.info("  - Purchases: %d", (df["event_name"] == "purchase").sum())
    logger.info("Files ready in data/ directory for Local mode.")


if __name__ == "__main__":
    main()
