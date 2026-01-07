#!/usr/bin/env python3
"""
Backfill asset_type in securities_prices_daily from securities_reference.

Purpose:
    Fixes Bronze data where asset_type is NULL in prices table by joining
    with securities_reference to get the correct asset_type for each ticker.

Usage:
    python -m scripts.maintenance.backfill_price_asset_type

    # Dry run (show what would change)
    python -m scripts.maintenance.backfill_price_asset_type --dry-run

    # Default asset type for unmatched tickers
    python -m scripts.maintenance.backfill_price_asset_type --default-type stocks
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def backfill_asset_type(
    dry_run: bool = False,
    default_type: str = "stocks"
):
    """
    Backfill asset_type in securities_prices_daily.

    Strategy:
    1. Read securities_reference to get ticker -> asset_type mapping
    2. Read securities_prices_daily
    3. Join to get asset_type for each ticker
    4. Overwrite the table with corrected data (using partition config from storage.json)
    """
    import json
    from pyspark.sql.functions import col, lit, coalesce, year as spark_year, month as spark_month

    # Load storage config (single source of truth for partitions)
    storage_json_path = repo_root / "configs" / "storage.json"
    with open(storage_json_path) as f:
        storage_cfg = json.load(f)

    # Initialize Spark with Delta support
    from orchestration.common.spark_session import get_spark
    spark = get_spark("BackfillPriceAssetType")

    # Paths
    bronze_root = repo_root / "storage" / "bronze"
    prices_path = bronze_root / "securities_prices_daily"
    reference_path = bronze_root / "securities_reference"

    logger.info("=" * 70)
    logger.info("BACKFILL asset_type IN securities_prices_daily")
    logger.info("=" * 70)

    # Check paths exist
    if not prices_path.exists():
        logger.error(f"Prices table not found: {prices_path}")
        return False
    if not reference_path.exists():
        logger.error(f"Reference table not found: {reference_path}")
        return False

    # Read tables (auto-detect Delta or Parquet)
    def read_table(spark, path):
        """Read table, auto-detecting Delta or Parquet format."""
        delta_log = path / "_delta_log"
        if delta_log.exists():
            return spark.read.format("delta").load(str(path)), "Delta"
        else:
            return spark.read.parquet(str(path)), "Parquet"

    logger.info(f"Reading prices from: {prices_path}")
    prices_df, prices_fmt = read_table(spark, prices_path)
    prices_count = prices_df.count()
    logger.info(f"  Total price rows: {prices_count:,} (format: {prices_fmt})")

    logger.info(f"Reading reference from: {reference_path}")
    ref_df, ref_fmt = read_table(spark, reference_path)
    ref_count = ref_df.count()
    logger.info(f"  Total reference rows: {ref_count:,} (format: {ref_fmt})")

    # Check current asset_type distribution
    logger.info("\nCurrent asset_type distribution in prices:")
    prices_df.groupBy("asset_type").count().show()

    # Get ticker -> asset_type mapping from reference
    # Use the most recent snapshot
    ticker_asset_map = (ref_df
        .select("ticker", "asset_type")
        .distinct()
        .withColumnRenamed("asset_type", "ref_asset_type"))

    logger.info(f"Unique tickers in reference: {ticker_asset_map.count():,}")

    # Show sample of mapping
    logger.info("\nSample ticker -> asset_type mapping:")
    ticker_asset_map.show(10)

    # Join prices with reference to get asset_type
    logger.info("\nJoining prices with reference...")
    updated_df = (prices_df
        .join(ticker_asset_map, on="ticker", how="left")
        .withColumn(
            "asset_type",
            coalesce(col("ref_asset_type"), col("asset_type"), lit(default_type))
        )
        .drop("ref_asset_type"))

    # Check updated distribution
    logger.info("\nUpdated asset_type distribution:")
    updated_df.groupBy("asset_type").count().show()

    # Count nulls before/after
    null_before = prices_df.filter(col("asset_type").isNull()).count()
    null_after = updated_df.filter(col("asset_type").isNull()).count()
    logger.info(f"NULL asset_type: {null_before:,} -> {null_after:,}")

    if dry_run:
        logger.info("\n" + "=" * 70)
        logger.info("DRY RUN - No changes made")
        logger.info("=" * 70)
        logger.info(f"Would update {null_before:,} rows with NULL asset_type")
        return True

    # Get partition config from storage.json (single source of truth)
    table_cfg = storage_cfg.get("tables", {}).get("securities_prices_daily", {})
    partition_cols = table_cfg.get("partitions", [])

    # Ensure partition columns exist in the data
    for pcol in partition_cols:
        if pcol == "year" and "year" not in updated_df.columns:
            updated_df = updated_df.withColumn("year", spark_year(col("trade_date")))
        if pcol == "month" and "month" not in updated_df.columns:
            updated_df = updated_df.withColumn("month", spark_month(col("trade_date")))

    # Write back as Delta (standard format)
    logger.info(f"\nWriting corrected data to: {prices_path}")
    logger.info("  Format: Delta")

    # Write as Delta (overwrite)
    # Note: Use coalesce to reduce file count
    writer = (updated_df
        .coalesce(100)  # Reduce to ~100 files for manageable size
        .write
        .format("delta")
        .mode("overwrite"))

    if partition_cols:
        logger.info(f"  Partitions: {partition_cols} (from storage.json)")
        writer = writer.partitionBy(*partition_cols)
    else:
        logger.info("  No partitions configured for securities_prices_daily in storage.json")

    writer.save(str(prices_path))

    logger.info("✓ Backfill complete!")

    # Verify
    logger.info("\nVerifying...")
    verify_df = spark.read.format("delta").load(str(prices_path))
    verify_df.groupBy("asset_type").count().show()

    spark.stop()
    return True


def main():
    """CLI entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Backfill asset_type in securities_prices_daily",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying data"
    )

    parser.add_argument(
        "--default-type",
        default="stocks",
        choices=["stocks", "etfs", "options", "futures"],
        help="Default asset_type for unmatched tickers (default: stocks)"
    )

    args = parser.parse_args()

    try:
        success = backfill_asset_type(
            dry_run=args.dry_run,
            default_type=args.default_type
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
