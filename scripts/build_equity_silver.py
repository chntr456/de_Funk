#!/usr/bin/env python3
"""
Build Equity Silver Layer from existing Bronze data.

This script:
1. Loads equity model configuration
2. Reads from Bronze (ref_ticker, prices_daily, exchanges, news)
3. Transforms and builds Silver tables
4. Writes parquet files to storage/silver/equity/

Usage:
    python scripts/build_equity_silver.py

Prerequisites:
    - Bronze data must exist (run ingestion first if needed)
    - Spark must be available for writes
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext
from models.api.session import UniversalSession
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    print("=" * 70)
    print("Building Equity Silver Layer")
    print("=" * 70)

    try:
        # Initialize with Spark (required for writes)
        print("\n1. Initializing Spark context...")
        ctx = RepoContext.from_repo_root(connection_type="spark")
        print("   ✓ Spark initialized")

        # Create session
        session = UniversalSession(
            connection=ctx.spark,
            storage_cfg=ctx.storage,
            repo_root=Path.cwd()
        )
        print("   ✓ Session created")

        # Load equity model
        print("\n2. Loading equity model configuration...")
        equity_model = session.get_model_instance('equity')
        print("   ✓ Equity model loaded")
        print(f"   Model type: {type(equity_model).__name__}")

        # Build Silver layer (in-memory DataFrames from Bronze)
        print("\n3. Building Silver tables from Bronze...")
        print("   Reading Bronze sources:")
        print("     - ref_ticker → dim_equity")
        print("     - exchanges → dim_exchange")
        print("     - prices_daily → fact_equity_prices")
        print("     - news → fact_equity_news")

        dims, facts = equity_model.build()

        print(f"\n   ✓ Built {len(dims)} dimension table(s):")
        for table_name in dims.keys():
            print(f"     - {table_name}")

        print(f"   ✓ Built {len(facts)} fact table(s):")
        for table_name in facts.keys():
            print(f"     - {table_name}")

        # Write to Silver parquet files
        print("\n4. Writing tables to Silver storage...")
        print("   Target: storage/silver/equity/")
        stats = equity_model.write_tables(use_optimized_writer=True)
        print("   ✓ Tables written successfully")

        # Report row counts
        print("\n5. Verifying Silver tables:")
        total_rows = 0
        for table_name, df in {**dims, **facts}.items():
            try:
                count = df.count()
                total_rows += count
                print(f"   ✓ {table_name}: {count:,} rows")
            except Exception as e:
                print(f"   ⚠ {table_name}: Unable to count rows ({e})")

        print(f"\n   Total: {total_rows:,} rows across all tables")

        print("\n" + "=" * 70)
        print("✓ Equity Silver layer built successfully!")
        print("=" * 70)
        print("\nSilver files location:")
        print("  storage/silver/equity/dims/")
        print("  storage/silver/equity/facts/")
        print("\nNext steps:")
        print("  1. Verify files: ls -la storage/silver/equity/")
        print("  2. Run examples: python examples/domain_strategy_measures_example.py")
        print("  3. View in UI: streamlit run app/ui/notebook_app_duckdb.py")

        ctx.spark.stop()
        return 0

    except FileNotFoundError as e:
        print(f"\n✗ ERROR: Bronze data not found")
        print(f"  {e}")
        print("\nPlease run ingestion first:")
        print("  python scripts/build_all_models.py --models equity --max-tickers 20")
        return 1

    except Exception as e:
        print(f"\n✗ ERROR: Failed to build Silver layer")
        print(f"  {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
