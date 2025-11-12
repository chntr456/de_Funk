#!/usr/bin/env python3
"""
Investigate ticker count discrepancy.

Checks:
1. How many unique tickers in fact_prices (actual traded stocks)
2. How many tickers in bronze.ref_ticker (reference data)
3. How many ended up in dim_company (after deduplication)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext

def main():
    print("="*80)
    print("TICKER COUNT INVESTIGATION")
    print("="*80)

    ctx = RepoContext.from_repo_root()

    # Check 1: Unique tickers in fact_prices
    print("\n1. UNIQUE TICKERS IN FACT_PRICES (Actual Traded Stocks)")
    print("-"*80)

    fact_prices_path = ctx.storage.root / "company" / "fact_prices"
    if fact_prices_path.exists():
        df = ctx.spark.read.parquet(str(fact_prices_path))
        total_rows = df.count()
        unique_tickers = df.select("ticker").distinct().count()

        print(f"Total price rows: {total_rows:,}")
        print(f"Unique tickers:   {unique_tickers:,}")
        print(f"Avg rows/ticker:  {total_rows/unique_tickers:,.1f}")

        # Show sample
        print("\nSample tickers:")
        df.select("ticker").distinct().orderBy("ticker").show(20, truncate=False)
    else:
        print("❌ fact_prices not found")

    # Check 2: Tickers in bronze.ref_ticker
    print("\n2. TICKERS IN BRONZE.REF_TICKER (Reference Data)")
    print("-"*80)

    ref_ticker_path = ctx.storage.bronze_root / "polygon" / "ref_ticker"
    if ref_ticker_path.exists():
        df = ctx.spark.read.parquet(str(ref_ticker_path))
        total_rows = df.count()

        # Check for duplicates
        if 'ticker' in df.columns:
            unique_tickers = df.select("ticker").distinct().count()
            duplicates = total_rows - unique_tickers

            print(f"Total rows:       {total_rows:,}")
            print(f"Unique tickers:   {unique_tickers:,}")
            print(f"Duplicates:       {duplicates:,}")

            if duplicates > 0:
                print(f"\n⚠️  Found {duplicates:,} duplicate tickers in bronze!")
                print("\nTop 10 duplicated tickers:")
                df.groupBy("ticker").count().filter("count > 1").orderBy("count", ascending=False).show(10)

                # Show details of one duplicate
                dup_ticker = df.groupBy("ticker").count().filter("count > 1").first()['ticker']
                print(f"\nDetails for duplicate ticker '{dup_ticker}':")
                df.filter(f"ticker = '{dup_ticker}'").show(truncate=False)
            else:
                print("✓ No duplicates")

            # Show sample
            print("\nSample ref_ticker data:")
            df.orderBy("ticker").show(10, truncate=False)
        else:
            print("Schema:")
            df.printSchema()
    else:
        print("❌ bronze.ref_ticker not found")

    # Check 3: Tickers in dim_company
    print("\n3. TICKERS IN DIM_COMPANY (After Deduplication)")
    print("-"*80)

    dim_company_path = ctx.storage.root / "company" / "dim_company"
    if dim_company_path.exists():
        df = ctx.spark.read.parquet(str(dim_company_path))
        total_rows = df.count()
        unique_tickers = df.select("ticker").distinct().count()
        duplicates = total_rows - unique_tickers

        print(f"Total rows:       {total_rows:,}")
        print(f"Unique tickers:   {unique_tickers:,}")
        print(f"Duplicates:       {duplicates:,}")

        if duplicates > 0:
            print(f"\n⚠️  STILL {duplicates:,} duplicates after deduplication!")
        else:
            print("✓ No duplicates (deduplication worked)")

        # Show sample
        print("\nSample dim_company data:")
        df.orderBy("ticker").show(10, truncate=False)
    else:
        print("❌ dim_company not found")

    # Check 4: Cross-reference
    print("\n4. CROSS-REFERENCE: PRICES vs DIM_COMPANY")
    print("-"*80)

    if fact_prices_path.exists() and dim_company_path.exists():
        prices_df = ctx.spark.read.parquet(str(fact_prices_path))
        dim_df = ctx.spark.read.parquet(str(dim_company_path))

        prices_tickers = prices_df.select("ticker").distinct()
        dim_tickers = dim_df.select("ticker").distinct()

        # Tickers in prices but not in dim
        missing_in_dim = prices_tickers.join(dim_tickers, "ticker", "left_anti").count()

        # Tickers in dim but not in prices
        extra_in_dim = dim_tickers.join(prices_tickers, "ticker", "left_anti").count()

        print(f"Tickers in prices but NOT in dim_company: {missing_in_dim:,}")
        print(f"Tickers in dim_company but NOT in prices: {extra_in_dim:,}")

        if missing_in_dim > 0:
            print("\n⚠️  Some traded stocks have no company dimension!")
            print("Sample missing tickers:")
            prices_tickers.join(dim_tickers, "ticker", "left_anti").show(10)

        if extra_in_dim > 0:
            print(f"\n✓ {extra_in_dim:,} reference tickers have no price data (normal)")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print()
    print("If dim_company has fewer tickers than expected, check:")
    print("1. Is bronze.ref_ticker being filtered during ingestion?")
    print("2. Is the deduplication logic dropping valid rows?")
    print("3. Is the bronze data incomplete?")
    print()

if __name__ == "__main__":
    main()
