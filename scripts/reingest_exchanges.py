#!/usr/bin/env python3
"""
Re-ingest exchanges data to get MIC codes from Polygon API.

This script re-ingests the exchanges reference data using the updated
ExchangesFacet which now extracts MIC codes (XNAS, XNYS, ARCX) instead
of numeric IDs. This fixes the auto-join issue where exchange_name was NULL.

Usage:
    python scripts/reingest_exchanges.py

    # Or with custom snapshot date
    python scripts/reingest_exchanges.py --snapshot 2025-11-12
"""

import sys
import argparse
from pathlib import Path
from datetime import date

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
from datapipelines.providers.polygon.facets.exchange_facet import ExchangesFacet


def reingest_exchanges(snapshot_dt: str = None):
    """
    Re-ingest exchanges data from Polygon API.

    Args:
        snapshot_dt: Optional snapshot date (YYYY-MM-DD). Defaults to today.
    """
    snap = snapshot_dt or date.today().isoformat()

    print("=" * 80)
    print("RE-INGEST EXCHANGES WITH MIC CODES")
    print("=" * 80)
    print(f"Snapshot date: {snap}")
    print("=" * 80)
    print()

    # Initialize context
    print("Step 1: Initializing context...")
    print("-" * 80)
    try:
        ctx = RepoContext.from_repo_root()
        print(f"  ✓ Context initialized")
        print(f"  ✓ Spark session: {ctx.spark.sparkContext.appName}")
    except Exception as e:
        print(f"  ✗ Failed to initialize context: {e}")
        sys.exit(1)
    print()

    # Initialize ingestor components
    print("Step 2: Setting up ingestor...")
    print("-" * 80)
    try:
        from datapipelines.ingestors.company_ingestor import CompanyPolygonIngestor
        from datapipelines.ingestors.bronze_sink import BronzeSink

        ingestor = CompanyPolygonIngestor(
            polygon_cfg=ctx.polygon_cfg,
            storage_cfg=ctx.storage,
            spark=ctx.spark
        )
        sink = BronzeSink(ctx.storage)
        print("  ✓ Ingestor initialized")
    except Exception as e:
        print(f"  ✗ Failed to initialize ingestor: {e}")
        sys.exit(1)
    print()

    # Check if partition exists
    print("Step 3: Checking existing data...")
    print("-" * 80)
    partition_exists = sink.exists("exchanges", {"snapshot_dt": snap})
    if partition_exists:
        print(f"  ⚠ Partition exists for snapshot_dt={snap}")
        print(f"  → Will DELETE and re-ingest with updated MIC codes")

        # Delete existing partition
        try:
            partition_path = sink._path("exchanges", {"snapshot_dt": snap})
            import shutil
            if partition_path.exists():
                shutil.rmtree(partition_path)
                print(f"  ✓ Deleted existing partition: {partition_path}")
        except Exception as e:
            print(f"  ✗ Failed to delete partition: {e}")
            sys.exit(1)
    else:
        print(f"  ✓ No existing partition for snapshot_dt={snap}")
    print()

    # Ingest exchanges
    print("Step 4: Ingesting exchanges from Polygon API...")
    print("-" * 80)
    try:
        ex_facet = ExchangesFacet(ctx.spark)
        print("  → Fetching exchanges from Polygon API...")
        ex_batches = ingestor._fetch_calls(ex_facet.calls())
        print(f"  ✓ Fetched {len(ex_batches)} batches")

        print("  → Normalizing data (extracting MIC codes)...")
        df_exchanges = ex_facet.normalize(ex_batches)

        # Show sample
        print("  ✓ Normalized exchanges:")
        df_exchanges.show(10, truncate=False)

        record_count = df_exchanges.count()
        print(f"  → Total exchanges: {record_count}")

        print(f"  → Writing to bronze layer...")
        sink.write_if_missing("exchanges", {"snapshot_dt": snap}, df_exchanges)
        print(f"  ✓ Written to bronze.exchanges (snapshot_dt={snap})")

    except Exception as e:
        print(f"  ✗ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    print()

    print("=" * 80)
    print("✓ EXCHANGES RE-INGESTION COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Rebuild dim_exchange in silver layer (run company model build)")
    print("  2. Run debug_exchange_data.py to verify MIC codes match")
    print("  3. Test dimensional selector exchange tab")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Re-ingest exchanges data to get MIC codes from Polygon API",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--snapshot',
        type=str,
        default=None,
        help='Snapshot date in YYYY-MM-DD format (default: today)'
    )

    args = parser.parse_args()

    try:
        reingest_exchanges(snapshot_dt=args.snapshot)
    except Exception as e:
        print(f"\n✗ Re-ingestion failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
