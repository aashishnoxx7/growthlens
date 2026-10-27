"""
Tests for growthlens.data_loader, schemas, and synthetic data generation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import pytest

from growthlens.config import DataSourceMode
from growthlens.data_loader import load_data, load_demo_data, load_local_file
from growthlens.schemas import REQUIRED_COLUMNS, SchemaValidationError, validate_events_df
from growthlens.synthetic import generate_demo_events


def test_generate_demo_events_deterministic():
    df1 = generate_demo_events(n_users=50, n_sessions=100, seed=42)
    df2 = generate_demo_events(n_users=50, n_sessions=100, seed=42)
    pd.testing.assert_frame_equal(df1, df2)


def test_generate_demo_events_has_required_columns():
    df = generate_demo_events(n_users=20, n_sessions=40, seed=1)
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"Missing required column: {col}"


def test_generate_demo_events_synthetic_labeling():
    df = generate_demo_events(n_users=10, n_sessions=20, seed=7)
    # Check that users are explicitly formatted as demo synthetic IDs
    assert df["user_pseudo_id"].str.startswith("demo_user_").all()


def test_load_demo_data_validates_schema():
    df = load_demo_data(seed=99)
    warnings = validate_events_df(df, "demo_test")
    assert isinstance(warnings, list)
    assert not df.empty


def test_load_local_file_csv(tmp_path):
    df_orig = generate_demo_events(n_users=10, n_sessions=20, seed=5)
    csv_file = tmp_path / "test_events.csv"
    df_orig.to_csv(csv_file, index=False)

    df_loaded = load_local_file(csv_file)
    assert len(df_loaded) == len(df_orig)
    assert "user_pseudo_id" in df_loaded.columns


def test_load_local_file_parquet(tmp_path):
    df_orig = generate_demo_events(n_users=10, n_sessions=20, seed=5)
    parquet_file = tmp_path / "test_events.parquet"
    df_orig.to_parquet(parquet_file, index=False)

    df_loaded = load_local_file(parquet_file)
    assert len(df_loaded) == len(df_orig)
    assert "user_pseudo_id" in df_loaded.columns


def test_load_local_file_missing():
    with pytest.raises(FileNotFoundError):
        load_local_file("non_existent_file.parquet")


def test_load_local_file_bad_extension(tmp_path):
    bad_file = tmp_path / "test_events.txt"
    bad_file.write_text("dummy")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        load_local_file(bad_file)


def test_load_data_demo_mode():
    df, label, warnings = load_data(mode=DataSourceMode.DEMO, seed=12)
    assert isinstance(df, pd.DataFrame)
    assert "DEMO" in label
    assert isinstance(warnings, list)


def test_schema_validation_missing_required_column():
    bad_df = pd.DataFrame({
        "event_date": ["2020-11-01"],
        # Missing event_name, event_timestamp, user_pseudo_id
    })
    with pytest.raises(SchemaValidationError, match="Missing required columns"):
        validate_events_df(bad_df, "bad_data")


def test_schema_validation_empty_df():
    with pytest.raises(SchemaValidationError, match="DataFrame is empty"):
        validate_events_df(pd.DataFrame(), "empty")
