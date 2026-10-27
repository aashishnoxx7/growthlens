"""
GrowthLens configuration — reads environment variables and .env file.
All sensitive values must come from environment; never hardcode secrets here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# ── Try to load .env if python-dotenv is available ────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass  # dotenv optional; env vars set by the shell are still picked up


# ── Project root ──────────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
EXPORTS_DIR: Path = PROJECT_ROOT / "exports"

# ── BigQuery ──────────────────────────────────────────────────────────────────
GCP_PROJECT: Optional[str] = os.getenv("GOOGLE_CLOUD_PROJECT")
BQ_MAX_BYTES_BILLED: int = int(os.getenv("BQ_MAX_BYTES_BILLED", "10000000000"))
BQ_SOURCE_PROJECT = "bigquery-public-data"
BQ_DATASET = "ga4_obfuscated_sample_ecommerce"
BQ_TABLE_WILDCARD = f"{BQ_SOURCE_PROJECT}.{BQ_DATASET}.events_*"

# Date bounds for the documented GA4 sample dataset
GA4_START_DATE = "20201101"
GA4_END_DATE = "20210131"

# ── Synthetic demo ────────────────────────────────────────────────────────────
DEMO_RANDOM_SEED: int = int(os.getenv("DEMO_RANDOM_SEED", "42"))
DEMO_N_USERS: int = 2_000
DEMO_N_SESSIONS: int = 5_000

# ── Funnel stages (in order) ──────────────────────────────────────────────────
FUNNEL_STAGES = [
    "view_item",
    "add_to_cart",
    "begin_checkout",
    "purchase",
]

FUNNEL_STAGE_LABELS = {
    "view_item": "Product Viewed",
    "add_to_cart": "Added to Cart",
    "begin_checkout": "Checkout Started",
    "purchase": "Purchase Completed",
}

# ── Data quality thresholds ───────────────────────────────────────────────────
MIN_SEGMENT_SIZE: int = 30          # minimum sessions for reliable rate comparison
REVENUE_OUTLIER_Z: float = 3.5      # z-score above which revenue is flagged

# ── Supported local file formats ──────────────────────────────────────────────
SUPPORTED_UPLOAD_EXTENSIONS = {".csv", ".parquet"}

# ── Data source modes ─────────────────────────────────────────────────────────
class DataSourceMode:
    BIGQUERY = "bigquery"
    LOCAL = "local"
    DEMO = "demo"


def bq_available() -> bool:
    """Return True when the BQ client library and a GCP project are configured."""
    try:
        from google.cloud import bigquery  # noqa: F401
        return bool(GCP_PROJECT)
    except ImportError:
        return False
