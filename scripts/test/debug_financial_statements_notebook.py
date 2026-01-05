#!/usr/bin/env python
"""
Debug script for financial statements notebook.

Simulates loading exhibits to identify join/data issues.
Uses deltalake for reading delta tables.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deltalake import DeltaTable
import pandas as pd


def read_table(table_path: Path):
    """Read a delta table using deltalake."""
    if not table_path.exists():
        return None

    try:
        dt = DeltaTable(str(table_path))
        return dt.to_pandas()
    except Exception as e:
        print(f"    Error reading {table_path}: {e}")
        return None


def check_bronze_tables(storage_root: Path):
    """Check bronze table availability and row counts."""
    print("\n" + "=" * 60)
    print("BRONZE LAYER CHECK")
    print("=" * 60)

    bronze_root = storage_root / "bronze"
    tables = [
        "securities_reference",
        "income_statements",
        "balance_sheets",
        "cash_flows",
        "earnings",
        "securities_prices_daily",
    ]

    for table in tables:
        table_path = bronze_root / table
        if table_path.exists():
            try:
                df = read_table(table_path)
                if df is not None:
                    count = len(df)
                    print(f"  {table}: {count:,} rows")
                    print(f"    Columns: {list(df.columns)[:8]}...")

                    # Show type distribution for securities_reference
                    if table == "securities_reference" and "type" in df.columns:
                        type_counts = df.groupby("type").size()
                        for type_val, count_val in type_counts.items():
                            print(f"    type='{type_val}': {count_val:,}")
            except Exception as e:
                print(f"  {table}: ERROR - {e}")
        else:
            print(f"  {table}: NOT FOUND at {table_path}")


def check_dim_company_simulation(storage_root: Path):
    """Simulate dim_company as defined in graph.yaml."""
    print("\n" + "=" * 60)
    print("DIM_COMPANY SIMULATION (from graph.yaml)")
    print("=" * 60)

    bronze_path = storage_root / "bronze" / "securities_reference"

    if not bronze_path.exists():
        print("  ERROR: securities_reference not found")
        return None

    try:
        df = read_table(bronze_path)
        if df is None:
            print("  ERROR: Could not read securities_reference")
            return None

        print(f"  Source rows: {len(df):,}")
        print(f"  Columns: {list(df.columns)}")

        # Check what type values exist
        if "type" in df.columns:
            print("\n  Type value distribution:")
            type_counts = df.groupby("type").size()
            for type_val, count_val in type_counts.items():
                print(f"    '{type_val}': {count_val:,}")

        # Check is_active values
        if "is_active" in df.columns:
            print("\n  is_active distribution:")
            active_counts = df.groupby("is_active").size()
            for val, count_val in active_counts.items():
                print(f"    {val}: {count_val:,}")

        # Apply filters from graph.yaml
        # Filter: type IN ('Stock', 'Common Stock') AND is_active = true
        if "type" in df.columns and "is_active" in df.columns:
            filtered = df[
                (df["type"].isin(["Stock", "Common Stock"])) &
                (df["is_active"] == True)
            ]
            print(f"\n  After graph.yaml filters: {len(filtered):,}")

            if len(filtered) > 0:
                print("\n  Sample dim_company rows:")
                cols = ["ticker", "security_name", "type", "is_active", "cik"]
                cols = [c for c in cols if c in filtered.columns]
                print(filtered[cols].head(10).to_string())

            return filtered
        else:
            print("  WARNING: Missing 'type' or 'is_active' columns")
            return df

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_fact_tables(storage_root: Path, dim_company_df):
    """Check fact tables and simulate joins."""
    print("\n" + "=" * 60)
    print("FACT TABLE CHECKS")
    print("=" * 60)

    fact_tables = {
        "income_statements": "fact_income_statement",
        "balance_sheets": "fact_balance_sheet",
        "cash_flows": "fact_cash_flow",
        "earnings": "fact_earnings",
    }

    for bronze_name, silver_name in fact_tables.items():
        print(f"\n  {bronze_name} -> {silver_name}:")

        bronze_path = storage_root / "bronze" / bronze_name

        if not bronze_path.exists():
            print(f"    NOT FOUND")
            continue

        try:
            df = read_table(bronze_path)
            if df is None:
                print(f"    ERROR: Could not read table")
                continue

            print(f"    Raw rows: {len(df):,}")
            print(f"    Columns: {list(df.columns)[:6]}...")

            # Check ticker distribution
            if "ticker" in df.columns:
                distinct_tickers = df["ticker"].nunique()
                print(f"    Distinct tickers: {distinct_tickers:,}")

                # Show sample tickers
                sample_tickers = df["ticker"].drop_duplicates().head(5).tolist()
                print(f"    Sample tickers: {sample_tickers}")

            # Simulate join with dim_company (via ticker)
            if dim_company_df is not None and "ticker" in df.columns and "ticker" in dim_company_df.columns:
                # Get lookup tickers
                lookup_tickers = set(dim_company_df["ticker"].dropna().unique())
                fact_tickers = set(df["ticker"].dropna().unique())

                matched = lookup_tickers & fact_tickers
                unmatched = fact_tickers - lookup_tickers

                print(f"    Tickers matching dim_company: {len(matched):,}")
                print(f"    Tickers NOT in dim_company: {len(unmatched):,}")

                if len(unmatched) > 0 and len(unmatched) <= 10:
                    print(f"    Unmatched tickers: {list(unmatched)[:10]}")

        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()


def simulate_notebook_filter(storage_root: Path, ticker: str = "AAPL"):
    """Simulate applying notebook filter for a specific ticker."""
    print("\n" + "=" * 60)
    print(f"NOTEBOOK FILTER SIMULATION (ticker={ticker})")
    print("=" * 60)

    # Check securities_reference
    bronze_path = storage_root / "bronze" / "securities_reference"
    try:
        df = read_table(bronze_path)
        if df is not None:
            ticker_rows = df[df["ticker"] == ticker]

            if len(ticker_rows) > 0:
                row = ticker_rows.iloc[0]
                print(f"  Found in securities_reference:")
                print(f"    ticker: {row.get('ticker')}")
                print(f"    type: {row.get('type')}")
                print(f"    is_active: {row.get('is_active')}")
                print(f"    cik: {row.get('cik')}")

                # Check if it passes the filter
                passes_filter = (
                    row.get('type') in ['Stock', 'Common Stock'] and
                    row.get('is_active') == True
                )
                print(f"    Passes dim_company filter: {passes_filter}")
            else:
                print(f"  NOT FOUND in securities_reference")
    except Exception as e:
        print(f"  ERROR checking securities_reference: {e}")

    # Check fact tables
    print(f"\n  Fact table rows for {ticker}:")
    fact_tables = ["income_statements", "balance_sheets", "cash_flows", "earnings"]

    for table in fact_tables:
        table_path = storage_root / "bronze" / table
        if table_path.exists():
            try:
                df = read_table(table_path)
                if df is not None:
                    count = len(df[df["ticker"] == ticker])
                    print(f"    {table}: {count:,} rows")
            except Exception as e:
                print(f"    {table}: ERROR - {e}")

    # Check stock prices
    prices_path = storage_root / "bronze" / "securities_prices_daily"
    if prices_path.exists():
        try:
            df = read_table(prices_path)
            if df is not None:
                count = len(df[df["ticker"] == ticker])
                print(f"    securities_prices_daily: {count:,} rows")
        except Exception as e:
            print(f"    securities_prices_daily: ERROR - {e}")


def check_silver_layer(storage_root: Path):
    """Check silver layer tables."""
    print("\n" + "=" * 60)
    print("SILVER LAYER CHECK")
    print("=" * 60)

    silver_root = storage_root / "silver"

    if not silver_root.exists():
        print("  Silver layer not found at", silver_root)
        print("  Run: python -m scripts.build.build_models")
        return

    for model_dir in sorted(silver_root.iterdir()):
        if model_dir.is_dir():
            print(f"\n  {model_dir.name}/")
            for table_dir in sorted(model_dir.iterdir()):
                if table_dir.is_dir():
                    try:
                        df = read_table(table_dir)
                        if df is not None:
                            count = len(df)
                            print(f"    {table_dir.name}: {count:,} rows")
                    except Exception as e:
                        print(f"    {table_dir.name}: ERROR - {e}")


def main():
    print("=" * 60)
    print("FINANCIAL STATEMENTS NOTEBOOK DEBUG")
    print("=" * 60)

    # Determine storage root
    storage_root = Path("/shared/storage")
    if not storage_root.exists():
        storage_root = Path(__file__).parent.parent.parent / "storage"

    print(f"Storage root: {storage_root}")

    if not storage_root.exists():
        print(f"ERROR: Storage root not found at {storage_root}")
        sys.exit(1)

    # Run checks
    check_bronze_tables(storage_root)

    dim_company = check_dim_company_simulation(storage_root)

    check_fact_tables(storage_root, dim_company)

    simulate_notebook_filter(storage_root, "AAPL")

    check_silver_layer(storage_root)

    print("\n" + "=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
