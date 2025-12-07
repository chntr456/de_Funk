#!/usr/bin/env python
"""
Quick workaround: Build just dim_stock for filter options.

This avoids the heavy window function calculations in fact_stock_prices.
Creates a lightweight stocks.dim_stock view in DuckDB.

Run: python -m scripts.setup.quick_dim_stock_view
"""
from __future__ import annotations

import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def main():
    """Create dim_stock view directly from Bronze, bypassing model build."""
    setup_logging()

    print("=" * 60)
    print("QUICK DIM_STOCK VIEW SETUP")
    print("=" * 60)
    print("This creates stocks.dim_stock view directly from Bronze")
    print("WITHOUT computing heavy window functions in fact_stock_prices")
    print()

    # Get Bronze path
    bronze_path = repo_root / "storage" / "bronze" / "securities_reference"

    if not bronze_path.exists():
        print(f"❌ Bronze layer not found: {bronze_path}")
        print("Run the ingestion pipeline first:")
        print("  python -m scripts.ingest.run_full_pipeline --max-tickers 100")
        return 1

    # Check if Delta or Parquet
    is_delta = (bronze_path / "_delta_log").exists()
    format_type = "Delta" if is_delta else "Parquet"
    print(f"✓ Found Bronze securities_reference ({format_type})")

    # Connect to DuckDB
    import duckdb

    db_path = repo_root / "storage" / "duckdb" / "analytics.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to: {db_path}")
    conn = duckdb.connect(str(db_path))

    # Install and load Delta extension if needed
    if is_delta:
        try:
            conn.execute("INSTALL delta")
            conn.execute("LOAD delta")
            print("✓ Delta extension loaded")
        except Exception as e:
            print(f"⚠ Delta extension not available: {e}")
            is_delta = False

    # Build read expression
    if is_delta:
        read_expr = f"delta_scan('{bronze_path}')"
    else:
        read_expr = f"read_parquet('{bronze_path}/**/*.parquet')"

    # Create stocks schema
    conn.execute("CREATE SCHEMA IF NOT EXISTS stocks")

    # Create dim_stock view with just the columns needed for filters
    # This is much faster than building the full model
    sql = f"""
    CREATE OR REPLACE VIEW stocks.dim_stock AS
    SELECT
        ticker,
        security_name AS name,
        type AS security_type,
        primary_exchange AS exchange_code,
        currency,
        is_active,
        cik,
        shares_outstanding,
        market_cap,
        sector,
        industry,
        -- Derive company_id for joins
        CONCAT('COMPANY_', LPAD(REGEXP_EXTRACT(cik, '([0-9]+)', 1), 10, '0')) AS company_id,
        -- Derive security_id
        SHA1(ticker) AS security_id
    FROM {read_expr}
    WHERE type = 'Common Stock'
      AND is_active = true
    """

    print("\nCreating stocks.dim_stock view...")
    try:
        conn.execute(sql)
        print("✓ View created successfully")
    except Exception as e:
        print(f"❌ Failed to create view: {e}")
        return 1

    # Validate
    result = conn.execute("SELECT COUNT(*) FROM stocks.dim_stock").fetchone()
    row_count = result[0]
    print(f"✓ Row count: {row_count:,}")

    # Show sample tickers
    tickers = conn.execute("""
        SELECT DISTINCT ticker
        FROM stocks.dim_stock
        WHERE ticker IS NOT NULL
        ORDER BY ticker
        LIMIT 10
    """).fetchall()
    print(f"✓ Sample tickers: {[t[0] for t in tickers]}")

    conn.close()

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"Created: stocks.dim_stock ({row_count:,} rows)")
    print()
    print("This view is lightweight and doesn't require building")
    print("the heavy fact_stock_prices with window functions.")
    print()
    print("To build the full Silver layer (with fact tables), use:")
    print("  python -m scripts.build_silver_layer")
    print()
    print("NOTE: This is a workaround. For production, use the full build.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
