"""
Data loader — the single entry point for obtaining events DataFrames.

Priority:
  1. Caller explicitly passes mode=DataSourceMode.BIGQUERY
  2. Caller explicitly passes mode=DataSourceMode.LOCAL  (file path required)
  3. mode=DataSourceMode.DEMO  — synthetic fallback

All returned DataFrames conform to the canonical schema defined in schemas.py.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from growthlens.config import DATA_DIR, DataSourceMode
from growthlens.schemas import SchemaValidationError, coerce_dtypes, validate_events_df
from growthlens.synthetic import generate_demo_events

logger = logging.getLogger(__name__)

# ── CSV / Parquet loading ─────────────────────────────────────────────────────

def load_local_file(path: Path | str) -> pd.DataFrame:
    """
    Load a CSV or Parquet file and return a canonical events DataFrame.

    Raises SchemaValidationError for structural problems.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Local file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, low_memory=False)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported file extension: {suffix}. Use .csv or .parquet")

    logger.info("Loaded local file '%s': %d rows, %d columns.", path.name, len(df), len(df.columns))
    df = coerce_dtypes(df)
    warnings = validate_events_df(df, source_label=path.name)
    for w in warnings:
        logger.warning("Schema warning [%s]: %s", path.name, w)
    return df


def list_local_data_files() -> list[Path]:
    """Return CSV/Parquet files in the data directory."""
    if not DATA_DIR.exists():
        return []
    return sorted(
        p for p in DATA_DIR.iterdir()
        if p.suffix.lower() in {".csv", ".parquet"}
    )


def load_demo_data(seed: int | None = None) -> pd.DataFrame:
    """Return the synthetic demonstration dataset."""
    kwargs = {}
    if seed is not None:
        kwargs["seed"] = seed
    df = generate_demo_events(**kwargs)
    df = coerce_dtypes(df)
    return df


def load_data(
    mode: str = DataSourceMode.DEMO,
    local_path: Optional[Path] = None,
    bq_start_date: Optional[str] = None,
    bq_end_date: Optional[str] = None,
    seed: Optional[int] = None,
) -> tuple[pd.DataFrame, str, list[str]]:
    """
    Unified data-loading function.

    Returns
    -------
    (df, source_label, warnings)
        df            : canonical events DataFrame
        source_label  : human-readable description of the data source
        warnings      : list of non-fatal schema warnings
    """
    warnings: list[str] = []

    if mode == DataSourceMode.BIGQUERY:
        try:
            from growthlens.bigquery_client import fetch_events_from_bq
            df = fetch_events_from_bq(
                start_date=bq_start_date,
                end_date=bq_end_date,
            )
            df = coerce_dtypes(df)
            warnings = validate_events_df(df, "BigQuery")
            source_label = "BigQuery — GA4 Obfuscated Sample Dataset"
        except Exception as exc:
            logger.error("BigQuery load failed: %s — falling back to DEMO.", exc)
            df = load_demo_data(seed=seed)
            source_label = "DEMO (BigQuery unavailable)"
            warnings.append(f"BigQuery load failed: {exc}")

    elif mode == DataSourceMode.LOCAL:
        if local_path is None:
            raise ValueError("local_path is required for LOCAL mode.")
        df = load_local_file(local_path)
        warnings = validate_events_df(df, str(local_path))
        source_label = f"Local file — {Path(local_path).name}"

    else:  # DEMO
        df = load_demo_data(seed=seed)
        warnings = validate_events_df(df, "synthetic demo")
        source_label = "DEMO — Synthetic Data (not real business performance)"

    logger.info("Data loaded: mode=%s, rows=%d, warnings=%d", mode, len(df), len(warnings))
    return df, source_label, warnings
