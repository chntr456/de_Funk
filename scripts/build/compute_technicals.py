#!/usr/bin/env python3
"""
Compute Technical Indicators in Batches.

This script adds technical indicators (SMA, RSI, Bollinger Bands, etc.) to
fact_stock_prices in batches to avoid OOM on large datasets.

The main stocks build now writes raw OHLCV data. This script runs after
to add derived technical columns in memory-efficient batches.

Usage:
    python -m scripts.build.compute_technicals
    python -m scripts.build.compute_technicals --batch-size 500 --storage-path /shared/storage

Architecture Note:
    Each batch processes N tickers at a time, computing all window functions
    for just those tickers. This keeps memory bounded regardless of total
    ticker count.

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Setup imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def get_all_security_ids(spark, prices_path: Path) -> List[int]:
    """Get list of all unique security_ids from prices table."""
    df = spark.read.parquet(str(prices_path))
    security_ids = [row.security_id for row in df.select("security_id").distinct().collect()]
    return sorted(security_ids)


def compute_technicals_for_batch(
    spark,
    prices_path: Path,
    output_path: Path,
    security_ids: List[int],
    batch_num: int,
    total_batches: int
) -> int:
    """
    Compute technical indicators for a batch of securities.

    Args:
        security_ids: List of security_id values to process in this batch

    Returns number of rows processed.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    logger.info(f"  Batch {batch_num}/{total_batches}: Processing {len(security_ids)} securities...")

    # Read only this batch's securities
    # Silver layer has: security_id, date_id, price_id, open, high, low, close, volume, adjusted_close
    # (no ticker or trade_date - those were dropped after deriving FKs)
    required_cols = ["date_id", "security_id", "price_id", "open", "high", "low", "close", "volume", "adjusted_close"]
    df = spark.read.parquet(str(prices_path)).select(*required_cols)
    df = df.filter(F.col("security_id").isin(security_ids))

    row_count = df.count()
    if row_count == 0:
        logger.warning(f"    No data for batch {batch_num}")
        return 0

    # Define window spec for each security ordered by date_id (integer YYYYMMDD format)
    # Note: Silver layer uses security_id (FK to dim_security) and date_id (FK to dim_calendar)
    security_window = Window.partitionBy("security_id").orderBy("date_id")

    # Rolling windows of different sizes
    window_20 = security_window.rowsBetween(-19, 0)
    window_50 = security_window.rowsBetween(-49, 0)
    window_200 = security_window.rowsBetween(-199, 0)
    window_14 = security_window.rowsBetween(-13, 0)
    window_60 = security_window.rowsBetween(-59, 0)

    # Compute technicals step by step to manage memory
    # Step 1: Daily return and price change
    df = df.withColumn(
        "prev_close",
        F.lag("close", 1).over(security_window)
    ).withColumn(
        "daily_return",
        F.when(F.col("prev_close").isNotNull() & (F.col("prev_close") != 0),
               (F.col("close") - F.col("prev_close")) / F.col("prev_close") * 100)
        .otherwise(None)
    ).withColumn(
        "price_change",
        F.col("close") - F.col("prev_close")
    )

    # Step 2: Simple Moving Averages
    df = df.withColumn("sma_20", F.avg("close").over(window_20))
    df = df.withColumn("sma_50", F.avg("close").over(window_50))
    df = df.withColumn("sma_200", F.avg("close").over(window_200))

    # Step 3: RSI components
    df = df.withColumn(
        "gain",
        F.when(F.col("price_change") > 0, F.col("price_change")).otherwise(0)
    ).withColumn(
        "loss",
        F.when(F.col("price_change") < 0, F.abs(F.col("price_change"))).otherwise(0)
    )

    df = df.withColumn("avg_gain_14", F.avg("gain").over(window_14))
    df = df.withColumn("avg_loss_14", F.avg("loss").over(window_14))

    df = df.withColumn(
        "rs_14",
        F.when(F.col("avg_loss_14") != 0, F.col("avg_gain_14") / F.col("avg_loss_14"))
        .otherwise(None)
    ).withColumn(
        "rsi_14",
        F.when(F.col("rs_14").isNotNull(), 100 - (100 / (1 + F.col("rs_14"))))
        .otherwise(50)  # Neutral RSI when undefined
    )

    # Step 4: Volatility
    df = df.withColumn("volatility_20d", F.stddev("daily_return").over(window_20) * (252 ** 0.5))
    df = df.withColumn("volatility_60d", F.stddev("daily_return").over(window_60) * (252 ** 0.5))

    # Step 5: Bollinger Bands
    df = df.withColumn("bollinger_middle", F.col("sma_20"))
    std_20 = F.stddev("close").over(window_20)
    df = df.withColumn("bollinger_upper", F.col("sma_20") + (2 * std_20))
    df = df.withColumn("bollinger_lower", F.col("sma_20") - (2 * std_20))

    # Step 6: Volume indicators
    df = df.withColumn("volume_sma_20", F.avg("volume").over(window_20))
    df = df.withColumn(
        "volume_ratio",
        F.when(F.col("volume_sma_20") != 0, F.col("volume") / F.col("volume_sma_20"))
        .otherwise(None)
    )

    # Drop intermediate columns
    df = df.drop("prev_close", "price_change", "gain", "loss", "avg_gain_14", "avg_loss_14", "rs_14")

    # Write batch (append mode for subsequent batches)
    mode = "overwrite" if batch_num == 1 else "append"
    df.coalesce(1).write.mode(mode).parquet(str(output_path))

    logger.info(f"    ✓ {row_count:,} rows processed")
    return row_count


def compute_technicals(
    storage_path: Path,
    batch_size: int = 500,
    dry_run: bool = False
) -> int:
    """
    Compute technical indicators for all stocks in batches.

    Args:
        storage_path: Root storage path
        batch_size: Number of tickers per batch
        dry_run: If True, just show what would be done

    Returns:
        Total rows processed
    """
    setup_logging()

    from orchestration.common.spark_session import get_spark

    prices_path = storage_path / "silver" / "stocks" / "facts" / "fact_stock_prices"
    output_path = storage_path / "silver" / "stocks" / "facts" / "fact_stock_prices_with_technicals"

    if not prices_path.exists():
        logger.error(f"Prices table not found: {prices_path}")
        return 0

    print("=" * 70)
    print("Computing Technical Indicators (Batched)")
    print("=" * 70)
    print()
    print(f"Input:  {prices_path}")
    print(f"Output: {output_path}")
    print(f"Batch size: {batch_size} tickers")
    print()

    # Initialize Spark with modest memory (we're batching)
    spark = get_spark("TechnicalsCompute", config={
        "spark.driver.memory": "4g",
        "spark.executor.memory": "4g",
    })

    # Get all security_ids (silver layer uses security_id not ticker)
    logger.info("Discovering securities...")
    all_security_ids = get_all_security_ids(spark, prices_path)
    total_securities = len(all_security_ids)
    logger.info(f"Found {total_securities:,} securities")

    # Calculate batches
    num_batches = (total_securities + batch_size - 1) // batch_size

    print(f"Total securities: {total_securities:,}")
    print(f"Batches: {num_batches}")
    print()

    if dry_run:
        print("DRY RUN - would process:")
        for i in range(min(3, num_batches)):
            start = i * batch_size
            end = min(start + batch_size, total_securities)
            print(f"  Batch {i+1}: securities {start+1}-{end}")
        if num_batches > 3:
            print(f"  ... and {num_batches - 3} more batches")
        spark.stop()
        return 0

    # Process batches
    total_rows = 0
    for i in range(num_batches):
        start = i * batch_size
        end = min(start + batch_size, total_securities)
        batch_security_ids = all_security_ids[start:end]

        rows = compute_technicals_for_batch(
            spark=spark,
            prices_path=prices_path,
            output_path=output_path,
            security_ids=batch_security_ids,
            batch_num=i + 1,
            total_batches=num_batches
        )
        total_rows += rows

    # Swap tables: move computed to original location
    import shutil

    logger.info("Finalizing...")
    backup_path = storage_path / "silver" / "stocks" / "facts" / "fact_stock_prices_backup"

    # Backup original
    if prices_path.exists():
        if backup_path.exists():
            shutil.rmtree(backup_path)
        shutil.move(str(prices_path), str(backup_path))

    # Move new to original location
    shutil.move(str(output_path), str(prices_path))

    # Remove backup
    if backup_path.exists():
        shutil.rmtree(backup_path)

    print()
    print("=" * 70)
    print("✓ Technical Indicators Complete")
    print("=" * 70)
    print(f"Total rows: {total_rows:,}")
    print(f"Output: {prices_path}")

    spark.stop()
    return total_rows


def main():
    parser = argparse.ArgumentParser(description="Compute technical indicators in batches")
    parser.add_argument(
        "--storage-path",
        type=str,
        default="/shared/storage",
        help="Storage root path"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of tickers per batch (default: 500)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )
    args = parser.parse_args()

    storage_path = Path(args.storage_path)
    compute_technicals(storage_path, batch_size=args.batch_size, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
