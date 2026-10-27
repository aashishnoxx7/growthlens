#!/usr/bin/env python3
"""
Ingest real-world commercial retail transactions (UCI / Databricks Online Retail Dataset)
and transform into the GrowthLens canonical event analytics format.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from datetime import timedelta
import numpy as np
import pandas as pd

# Add src to python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from growthlens.config import DATA_DIR
from growthlens.schemas import coerce_dtypes, validate_events_df

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_real_retail")

DATASET_URL = "https://raw.githubusercontent.com/databricks/Spark-The-Definitive-Guide/master/data/retail-data/all/online-retail-dataset.csv"


def download_and_transform(max_invoices: int = 4000) -> pd.DataFrame:
    logger.info("Downloading real-world commercial retail data from GitHub (Databricks mirror)...")
    raw_df = pd.read_csv(DATASET_URL)
    logger.info("Raw data loaded: %d rows across %d invoices.", len(raw_df), raw_df["InvoiceNo"].nunique())

    # Filter out cancellations and negative prices
    valid = raw_df[(raw_df["Quantity"] > 0) & (raw_df["UnitPrice"] > 0) & (~raw_df["InvoiceNo"].astype(str).str.startswith("C"))].copy()
    valid["LineRevenue"] = valid["Quantity"] * valid["UnitPrice"]
    valid["InvoiceDate"] = pd.to_datetime(valid["InvoiceDate"], errors="coerce", utc=True)
    valid = valid.dropna(subset=["InvoiceDate"])

    # Aggregate by Invoice
    logger.info("Aggregating into transaction sessions...")
    invoices = valid.groupby("InvoiceNo").agg(
        invoice_date=("InvoiceDate", "first"),
        customer_id=("CustomerID", "first"),
        total_revenue=("LineRevenue", "sum"),
        item_count=("Quantity", "sum"),
        top_product=("Description", "first"),
        country=("Country", "first"),
    ).reset_index()

    # Limit to reasonable sample size if requested
    if max_invoices and len(invoices) > max_invoices:
        invoices = invoices.head(max_invoices)

    logger.info("Processing %d real commercial orders...", len(invoices))

    rng = np.random.default_rng(42)
    sources = ["google", "direct", "facebook", "email", "bing"]
    source_p = [0.42, 0.30, 0.14, 0.08, 0.06]
    medium_map = {"google": "organic", "direct": "(none)", "facebook": "cpc", "email": "email", "bing": "cpc"}
    devices = ["mobile", "desktop", "tablet"]
    device_p = [0.52, 0.40, 0.08]

    all_events = []

    # 1. Generate full funnel events for real purchasers
    for _, inv in invoices.iterrows():
        inv_no = str(inv["InvoiceNo"])
        cust_id = f"cust_{int(inv['customer_id'])}" if pd.notna(inv["customer_id"]) else f"guest_{inv_no}"
        session_id = f"sess_{inv_no}"
        session_key = f"{cust_id}_{session_id}"

        ts = inv["invoice_date"]
        device = rng.choice(devices, p=device_p)
        source = rng.choice(sources, p=source_p)
        medium = medium_map[source]
        revenue = float(round(inv["total_revenue"], 2))

        # Funnel timestamps in strict chronological order
        t_start = ts - timedelta(minutes=int(rng.integers(12, 30)))
        t_view = t_start + timedelta(minutes=int(rng.integers(2, 6)))
        t_cart = t_view + timedelta(minutes=int(rng.integers(2, 5)))
        t_checkout = t_cart + timedelta(minutes=int(rng.integers(2, 4)))
        t_purchase = ts

        base = {
            "user_pseudo_id": cust_id,
            "session_id": session_id,
            "session_key": session_key,
            "device_category": device,
            "traffic_source": source,
            "traffic_medium": medium,
            "traffic_campaign": "(not set)",
            "revenue": None,
            "transaction_id": None,
        }

        # Step 1: session_start
        all_events.append({**base, "event_date": t_start.strftime("%Y-%m-%d"), "event_timestamp": t_start, "event_name": "session_start"})
        # Step 2: view_item
        all_events.append({**base, "event_date": t_view.strftime("%Y-%m-%d"), "event_timestamp": t_view, "event_name": "view_item"})
        # Step 3: add_to_cart
        all_events.append({**base, "event_date": t_cart.strftime("%Y-%m-%d"), "event_timestamp": t_cart, "event_name": "add_to_cart"})
        # Step 4: begin_checkout
        all_events.append({**base, "event_date": t_checkout.strftime("%Y-%m-%d"), "event_timestamp": t_checkout, "event_name": "begin_checkout"})
        # Step 5: purchase
        all_events.append({**base, "event_date": t_purchase.strftime("%Y-%m-%d"), "event_timestamp": t_purchase, "event_name": "purchase", "revenue": revenue, "transaction_id": inv_no})

    # 2. Add realistic non-converting / drop-off sessions to reflect true ecommerce behavior
    n_abandoned = int(len(invoices) * 2.5)
    logger.info("Synthesizing %d realistic browsing and abandoned cart sessions...", n_abandoned)

    min_ts = invoices["invoice_date"].min()
    max_ts = invoices["invoice_date"].max()
    span_seconds = int((max_ts - min_ts).total_seconds())

    for i in range(n_abandoned):
        inv_no = f"browse_{i:06d}"
        cust_id = f"cust_visitor_{rng.integers(1000, 9999)}"
        session_id = f"sess_{inv_no}"
        session_key = f"{cust_id}_{session_id}"

        offset = int(rng.integers(0, span_seconds))
        t_start = min_ts + timedelta(seconds=offset)
        device = rng.choice(devices, p=device_p)
        source = rng.choice(sources, p=source_p)
        medium = medium_map[source]

        base = {
            "user_pseudo_id": cust_id,
            "session_id": session_id,
            "session_key": session_key,
            "device_category": device,
            "traffic_source": source,
            "traffic_medium": medium,
            "traffic_campaign": "(not set)",
            "revenue": None,
            "transaction_id": None,
        }

        all_events.append({**base, "event_date": t_start.strftime("%Y-%m-%d"), "event_timestamp": t_start, "event_name": "session_start"})

        # 70% view an item
        if rng.random() < 0.70:
            t_view = t_start + timedelta(minutes=int(rng.integers(1, 5)))
            all_events.append({**base, "event_date": t_view.strftime("%Y-%m-%d"), "event_timestamp": t_view, "event_name": "view_item"})

            # 35% of those add to cart
            if rng.random() < 0.35:
                t_cart = t_view + timedelta(minutes=int(rng.integers(2, 6)))
                all_events.append({**base, "event_date": t_cart.strftime("%Y-%m-%d"), "event_timestamp": t_cart, "event_name": "add_to_cart"})

                # 40% of those begin checkout but abandon
                if rng.random() < 0.40:
                    t_checkout = t_cart + timedelta(minutes=int(rng.integers(2, 4)))
                    all_events.append({**base, "event_date": t_checkout.strftime("%Y-%m-%d"), "event_timestamp": t_checkout, "event_name": "begin_checkout"})

    events_df = pd.DataFrame(all_events)
    events_df = coerce_dtypes(events_df)
    events_df = events_df.sort_values(["event_timestamp", "user_pseudo_id"]).reset_index(drop=True)

    validate_events_df(events_df, "Real Retail Dataset")
    return events_df


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    events_df = download_and_transform(max_invoices=4000)

    parquet_path = DATA_DIR / "real_retail_events.parquet"
    csv_path = DATA_DIR / "real_retail_events.csv"

    logger.info("Saving to Parquet: %s", parquet_path)
    events_df.to_parquet(parquet_path, index=False)

    logger.info("Saving to CSV: %s", csv_path)
    events_df.to_csv(csv_path, index=False)

    total_rev = events_df.loc[events_df["event_name"] == "purchase", "revenue"].sum()
    logger.info("✅ SUCCESS! Real retail dataset ready:")
    logger.info("  - Total Events: %d", len(events_df))
    logger.info("  - Distinct Users: %d", events_df["user_pseudo_id"].nunique())
    logger.info("  - Distinct Sessions: %d", events_df["session_key"].nunique())
    logger.info("  - Total Real Purchases: %d", (events_df["event_name"] == "purchase").sum())
    logger.info("  - Total Real Revenue: $%.2f", total_rev)


if __name__ == "__main__":
    main()
