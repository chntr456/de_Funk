#!/usr/bin/env python3
"""
Build Equity Silver Layer from Bronze data using DuckDB.

This script:
1. Loads equity model configuration
2. Reads from Bronze (ref_ticker, prices_daily, exchanges)
3. Transforms and builds Silver tables using DuckDB
4. Writes parquet files to storage/silver/equity/

Usage:
    python scripts/build_equity_silver_duckdb.py

Prerequisites:
    - Bronze data must exist
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext
import duckdb
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("Building Equity Silver Layer (DuckDB)")
    print("=" * 70)

    try:
        # Initialize DuckDB context
        print("\n1. Initializing DuckDB context...")
        ctx = RepoContext.from_repo_root(connection_type="duckdb")
        conn = ctx.connection.conn
        print("   ✓ DuckDB initialized")

        # Define paths
        bronze_root = Path("storage/bronze")
        silver_root = Path("storage/silver/equity")
        silver_root.mkdir(parents=True, exist_ok=True)

        print(f"\n2. Reading Bronze data from {bronze_root}...")

        # Build dim_equity from ref_ticker
        print("\n   Building dim_equity from ref_ticker...")
        dim_equity_df = conn.execute(f"""
            SELECT DISTINCT
                ticker,
                name AS company_name,
                exchange_code,
                NULL AS company_id,
                NULL AS security_type,
                NULL AS currency,
                TRUE AS is_active,
                NULL AS listing_date,
                NULL AS delisting_date,
                NULL AS shares_outstanding,
                CURRENT_TIMESTAMP AS last_updated
            FROM read_parquet('{bronze_root}/ref_ticker/**/*.parquet')
        """).fetch_df()
        print(f"   ✓ dim_equity: {len(dim_equity_df):,} rows")

        # Build dim_exchange from exchanges
        print("\n   Building dim_exchange from exchanges...")
        dim_exchange_df = conn.execute(f"""
            SELECT DISTINCT
                code AS exchange_code,
                name AS exchange_name,
                NULL AS country,
                NULL AS timezone
            FROM read_parquet('{bronze_root}/exchanges/**/*.parquet')
        """).fetch_df()
        print(f"   ✓ dim_exchange: {len(dim_exchange_df):,} rows")

        # Build fact_equity_prices from prices_daily
        print("\n   Building fact_equity_prices from prices_daily...")
        fact_equity_prices_df = conn.execute(f"""
            SELECT
                ticker,
                CAST(trade_date AS DATE) AS trade_date,
                open,
                high,
                low,
                close,
                volume,
                volume_weighted AS vwap,
                NULL AS num_trades,
                CURRENT_TIMESTAMP AS ingestion_ts
            FROM read_parquet('{bronze_root}/prices_daily/**/*.parquet')
        """).fetch_df()
        print(f"   ✓ fact_equity_prices: {len(fact_equity_prices_df):,} rows")

        # Write to Silver storage
        print("\n3. Writing tables to Silver storage...")

        # Create directories
        (silver_root / "dims" / "dim_equity").mkdir(parents=True, exist_ok=True)
        (silver_root / "dims" / "dim_exchange").mkdir(parents=True, exist_ok=True)
        (silver_root / "facts" / "fact_equity_prices").mkdir(parents=True, exist_ok=True)

        # Write dim_equity
        dim_equity_path = silver_root / "dims" / "dim_equity" / "data.parquet"
        conn.execute(f"""
            COPY (SELECT * FROM dim_equity_df)
            TO '{dim_equity_path}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)
        print(f"   ✓ Written: {dim_equity_path}")

        # Write dim_exchange
        dim_exchange_path = silver_root / "dims" / "dim_exchange" / "data.parquet"
        conn.execute(f"""
            COPY (SELECT * FROM dim_exchange_df)
            TO '{dim_exchange_path}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)
        print(f"   ✓ Written: {dim_exchange_path}")

        # Write fact_equity_prices
        fact_equity_prices_path = silver_root / "facts" / "fact_equity_prices" / "data.parquet"
        conn.execute(f"""
            COPY (SELECT * FROM fact_equity_prices_df)
            TO '{fact_equity_prices_path}'
            (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)
        print(f"   ✓ Written: {fact_equity_prices_path}")

        print("\n" + "=" * 70)
        print("✓ Equity Silver layer built successfully!")
        print("=" * 70)
        print("\nSilver files location:")
        print(f"  {silver_root}/dims/")
        print(f"  {silver_root}/facts/")
        print("\nNext steps:")
        print("  1. Run tests: python examples/comprehensive_test.py")
        print("  2. Run examples: python examples/query_planner_example.py")

        conn.close()
        return 0

    except Exception as e:
        print(f"\n✗ ERROR: Failed to build Silver layer")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
