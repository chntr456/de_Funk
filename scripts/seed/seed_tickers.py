#!/usr/bin/env python3
"""
Seed Tickers from Alpha Vantage LISTING_STATUS.

Fetches ALL active US tickers from Alpha Vantage in ONE API call and writes
to Bronze layer. This seeds the securities_reference table that the
distributed pipeline uses for ticker discovery.

Usage:
    python -m scripts.seed.seed_tickers
    python -m scripts.seed.seed_tickers --storage-path /shared/storage

This should be run BEFORE the distributed pipeline to populate the ticker list.
"""

import argparse
from pathlib import Path

from utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from orchestration.common.spark_session import get_spark
from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def seed_tickers(storage_path: Path = None, force: bool = False) -> int:
    """
    Seed tickers from Alpha Vantage LISTING_STATUS.

    Args:
        storage_path: Optional storage root (default: repo_root/storage)
        force: Force re-seed even if data exists

    Returns:
        Number of tickers seeded
    """
    setup_logging()

    # Determine storage path
    if storage_path is None:
        storage_path = repo_root / "storage"
    storage_path = Path(storage_path)

    bronze_path = storage_path / "bronze" / "securities_reference"

    # Check if already exists (unless force)
    if not force and bronze_path.exists() and (bronze_path / "_delta_log").exists():
        spark = get_spark("TickerSeedCheck")
        try:
            existing_df = spark.read.format("delta").load(str(bronze_path))
            existing_count = existing_df.count()
            if existing_count > 100:  # More than just test data
                print(f"✓ Tickers already seeded: {existing_count:,} tickers at {bronze_path}")
                print("  Use --force to re-seed")
                spark.stop()
                return existing_count
        except Exception:
            pass
        finally:
            spark.stop()

    print("=" * 70)
    print("Seeding Tickers from Alpha Vantage LISTING_STATUS")
    print("=" * 70)
    print()
    print("This makes ONE API call to fetch ALL active US tickers.")
    print()

    # Initialize Spark
    print("1. Initializing Spark...")
    spark = get_spark("TickerSeed")
    print()

    # Initialize ingestor
    print("2. Initializing Alpha Vantage ingestor...")
    from core.context import RepoContext
    from datapipelines.providers.alpha_vantage.alpha_vantage_ingestor import AlphaVantageIngestor

    ctx = RepoContext.from_repo_root(repo_root)
    ingestor = AlphaVantageIngestor(ctx)
    print()

    # Fetch bulk listing
    print("3. Fetching ALL tickers from LISTING_STATUS (1 API call)...")
    print("-" * 70)

    # Call the bulk listing method
    df, all_tickers, ticker_exchanges = ingestor.ingest_bulk_listing(
        table_name="securities_reference",
        state="active"
    )

    if df is None or len(all_tickers) == 0:
        print("ERROR: No tickers returned from LISTING_STATUS")
        spark.stop()
        return 0

    # Filter to US exchanges
    us_exchanges = ["NYSE", "NASDAQ", "NYSEAMERICAN", "NYSEMKT", "BATS", "NYSEARCA"]
    us_tickers = [t for t in all_tickers if ticker_exchanges.get(t) in us_exchanges]

    print()
    print(f"   Total tickers from LISTING_STATUS: {len(all_tickers):,}")
    print(f"   US exchange tickers: {len(us_tickers):,}")
    print(f"   Foreign exchange tickers (excluded): {len(all_tickers) - len(us_tickers):,}")
    print()

    # Write to Bronze (the ingestor already wrote it, but let's verify path)
    print("4. Verifying Bronze data...")

    # Re-read to verify and get count
    from datapipelines.ingestors.bronze_sink import BronzeSink
    sink = BronzeSink(spark, str(storage_path / "bronze"))

    # Filter the dataframe to US exchanges and write
    from pyspark.sql.functions import col
    df_us = df.filter(col("exchange_code").isin(us_exchanges))

    # Write to the correct path
    sink.smart_write(df_us, "securities_reference")

    # Verify
    verify_df = spark.read.format("delta").load(str(bronze_path))
    ticker_count = verify_df.count()

    print(f"   ✓ Written {ticker_count:,} US tickers to {bronze_path}")
    print()

    # Show sample
    print("5. Sample tickers:")
    verify_df.select("ticker", "security_name", "exchange_code", "asset_type").show(10, truncate=False)

    # Show exchange breakdown
    print("6. Exchange breakdown:")
    verify_df.groupBy("exchange_code").count().orderBy("count", ascending=False).show()

    print("=" * 70)
    print("Ticker seed complete!")
    print("=" * 70)
    print()
    print(f"Total US tickers available: {ticker_count:,}")
    print()
    print("You can now run the full pipeline:")
    print("  ./scripts/cluster/run_production.sh")
    print()

    spark.stop()
    return ticker_count


def main():
    parser = argparse.ArgumentParser(description="Seed tickers from Alpha Vantage LISTING_STATUS")
    parser.add_argument(
        "--storage-path",
        type=str,
        default=None,
        help="Storage root path (default: repo_root/storage)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-seed even if data exists"
    )
    args = parser.parse_args()

    storage_path = Path(args.storage_path) if args.storage_path else None
    seed_tickers(storage_path, force=args.force)


if __name__ == "__main__":
    main()
