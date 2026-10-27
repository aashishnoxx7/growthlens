#!/usr/bin/env python3
"""
Command-line data quality validator for GrowthLens event datasets.
Runs all 12 automated checks and reports summary status, issue counts, and remediation actions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd

from growthlens.data_loader import load_data, load_local_file
from growthlens.data_quality import quality_summary, run_all_quality_checks


def parse_args():
    parser = argparse.ArgumentParser(description="Run GrowthLens data quality checks.")
    parser.add_argument("--file", help="Path to local CSV or Parquet file. Defaults to Demo data if omitted.")
    parser.add_argument("--output", help="Optional path to export report CSV.")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.file:
        file_path = Path(args.file)
        print(f"Loading data from {file_path}...")
        df = load_local_file(file_path)
    else:
        print("Loading synthetic demo data...")
        df, _, _ = load_data(mode="demo")

    print(f"Loaded {len(df):,} event records. Running 12 quality checks...\n")
    results = run_all_quality_checks(df)
    summary = quality_summary(results)

    status_symbol = "✅" if summary["overall_status"] == "pass" else "⚠️" if summary["overall_status"] == "warn" else "❌"
    print(f"{status_symbol} Overall Quality Status: {summary['overall_status'].upper()}")
    print(f"  - Total Checks: {summary['total_checks']}")
    print(f"  - Passed:       {summary['passes']}")
    print(f"  - Warnings:     {summary['warnings']}")
    print(f"  - Errors:       {summary['errors']}\n")

    print(f"{'CHECK NAME':<26} {'SEVERITY':<10} {'STATUS':<8} {'AFFECTED':<12} {'%':<8} {'MESSAGE'}")
    print("-" * 100)
    for r in results:
        pct_str = f"{r['pct_affected']:.2f}%"
        print(f"{r['check_name']:<26} {r['severity'].upper():<10} {r['status'].upper():<8} {r['affected_rows']:<12,d} {pct_str:<8} {r['message'][:40]}...")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(results).to_csv(out_path, index=False)
        print(f"\nFull report written to {out_path}")


if __name__ == "__main__":
    main()
