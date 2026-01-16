#!/usr/bin/env python3
"""
Compute Technical Indicators using Native Spark Window Functions.

This script adds technical indicators (SMA, RSI, Bollinger Bands, etc.) to
fact_stock_prices using Spark's native window functions. Spark handles
memory management automatically via partitioning - NO Python-level batching needed.

Usage:
    python -m scripts.build.compute_technicals
    python -m scripts.build.compute_technicals --storage-path /shared/storage

Architecture Note:
    Spark's window functions with partitionBy("ticker") handle memory automatically.
    Each partition is processed independently, allowing Spark to spill to disk
    if needed. This scales to millions of rows without manual batching.

Note:
    This script reads from Delta format (the default silver layer format).
    If the table was written as Delta, it will be read as Delta.

Author: de_Funk Team
Date: January 2026 (rewritten to remove unnecessary batching)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Setup imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def compute_technicals(
    storage_path: Path,
    dry_run: bool = False
) -> int:
    """
    Compute technical indicators for all stocks using native Spark windowing.

    Spark handles memory automatically via partitioning. No Python batching needed.

    Args:
        storage_path: Root storage path
        dry_run: If True, just show what would be done

    Returns:
        Total rows processed
    """
    setup_logging()

    from pyspark.sql import functions as F
    from pyspark.sql.window import Window
    from orchestration.common.spark_session import get_spark

    # Paths - fact_stock_prices is in silver layer
    # After the derive/drop refactor, this table has:
    # - price_id, security_id, date_id (FK columns)
    # - open, high, low, close, volume, adjusted_close (price data)
    # NOTE: ticker and trade_date are DROPPED - use security_id and date_id
    silver_root = storage_path / "silver" / "stocks" / "facts"
    prices_path = silver_root / "fact_stock_prices"

    if not prices_path.exists():
        logger.error(f"Prices table not found: {prices_path}")
        return 0

    print("=" * 70)
    print("Computing Technical Indicators (Native Spark)")
    print("=" * 70)
    print()
    print(f"Input/Output: {prices_path}")
    print()

    # Check if Delta or Parquet
    is_delta = (prices_path / "_delta_log").exists()
    format_type = "delta" if is_delta else "parquet"
    print(f"Format: {format_type}")

    # Initialize Spark (memory is handled by Spark automatically)
    spark = get_spark("TechnicalsCompute")

    # Read the prices table
    logger.info("Loading price data...")
    if is_delta:
        df = spark.read.format("delta").load(str(prices_path))
    else:
        df = spark.read.parquet(str(prices_path))

    # Show schema for debugging
    print("\nInput schema:")
    df.printSchema()

    # Check what columns we have
    cols = df.columns
    print(f"\nColumns: {cols}")

    # Determine the partition column and order column
    # New schema (post-refactor): security_id, date_id
    # Old schema (pre-refactor): ticker, trade_date
    if 'security_id' in cols and 'date_id' in cols:
        partition_col = "security_id"
        order_col = "date_id"
        print(f"\nUsing new schema: partition by {partition_col}, order by {order_col}")
    elif 'ticker' in cols and 'trade_date' in cols:
        partition_col = "ticker"
        order_col = "trade_date"
        print(f"\nUsing legacy schema: partition by {partition_col}, order by {order_col}")
    else:
        logger.error(f"Cannot determine partition/order columns from schema: {cols}")
        spark.stop()
        return 0

    row_count = df.count()
    distinct_count = df.select(partition_col).distinct().count()

    print(f"\nTotal rows: {row_count:,}")
    print(f"Distinct {partition_col}s: {distinct_count:,}")
    print()

    if dry_run:
        print("DRY RUN - would compute technicals for all securities")
        spark.stop()
        return 0

    logger.info("Computing technical indicators...")

    # Define window specs - Spark handles partitioning automatically
    # Each partition (ticker/security_id) is processed independently
    security_window = Window.partitionBy(partition_col).orderBy(order_col)

    # Rolling windows of different sizes
    window_14 = security_window.rowsBetween(-13, 0)
    window_20 = security_window.rowsBetween(-19, 0)
    window_50 = security_window.rowsBetween(-49, 0)
    window_60 = security_window.rowsBetween(-59, 0)
    window_200 = security_window.rowsBetween(-199, 0)

    # ===========================================
    # Step 1: Daily return and price change
    # ===========================================
    print("  Computing returns...")
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

    # ===========================================
    # Step 2: Simple Moving Averages
    # ===========================================
    print("  Computing SMAs (20, 50, 200)...")
    df = (df
        .withColumn("sma_20", F.avg("close").over(window_20))
        .withColumn("sma_50", F.avg("close").over(window_50))
        .withColumn("sma_200", F.avg("close").over(window_200))
    )

    # ===========================================
    # Step 3: RSI (Relative Strength Index)
    # ===========================================
    print("  Computing RSI...")
    df = (df
        .withColumn(
            "gain",
            F.when(F.col("price_change") > 0, F.col("price_change")).otherwise(0)
        )
        .withColumn(
            "loss",
            F.when(F.col("price_change") < 0, F.abs(F.col("price_change"))).otherwise(0)
        )
        .withColumn("avg_gain_14", F.avg("gain").over(window_14))
        .withColumn("avg_loss_14", F.avg("loss").over(window_14))
        .withColumn(
            "rs_14",
            F.when(F.col("avg_loss_14") != 0, F.col("avg_gain_14") / F.col("avg_loss_14"))
            .otherwise(None)
        )
        .withColumn(
            "rsi_14",
            F.when(F.col("rs_14").isNotNull(), 100 - (100 / (1 + F.col("rs_14"))))
            .otherwise(50)  # Neutral RSI when undefined
        )
    )

    # ===========================================
    # Step 4: Volatility
    # ===========================================
    print("  Computing volatility...")
    df = (df
        .withColumn("volatility_20d", F.stddev("daily_return").over(window_20) * (252 ** 0.5))
        .withColumn("volatility_60d", F.stddev("daily_return").over(window_60) * (252 ** 0.5))
    )

    # ===========================================
    # Step 5: Bollinger Bands
    # ===========================================
    print("  Computing Bollinger Bands...")
    std_20 = F.stddev("close").over(window_20)
    df = (df
        .withColumn("bollinger_middle", F.col("sma_20"))
        .withColumn("bollinger_upper", F.col("sma_20") + (2 * std_20))
        .withColumn("bollinger_lower", F.col("sma_20") - (2 * std_20))
    )

    # ===========================================
    # Step 6: Volume indicators
    # ===========================================
    print("  Computing volume indicators...")
    df = (df
        .withColumn("volume_sma_20", F.avg("volume").over(window_20))
        .withColumn(
            "volume_ratio",
            F.when(F.col("volume_sma_20") != 0, F.col("volume") / F.col("volume_sma_20"))
            .otherwise(None)
        )
    )

    # ===========================================
    # Drop intermediate columns
    # ===========================================
    df = df.drop("prev_close", "price_change", "gain", "loss", "avg_gain_14", "avg_loss_14", "rs_14")

    # ===========================================
    # Write back to same location (overwrite)
    # ===========================================
    print("\n  Writing results...")
    logger.info(f"Writing {row_count:,} rows with technical indicators...")

    # Use Delta format if original was Delta, otherwise parquet
    if is_delta:
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(str(prices_path))
    else:
        df.write.mode("overwrite").parquet(str(prices_path))

    print()
    print("=" * 70)
    print("Technical Indicators Complete")
    print("=" * 70)
    print(f"Total rows: {row_count:,}")
    print(f"Securities: {distinct_count:,}")
    print(f"Output: {prices_path}")

    spark.stop()
    return row_count


def main():
    parser = argparse.ArgumentParser(
        description="Compute technical indicators using native Spark windowing"
    )
    parser.add_argument(
        "--storage-path",
        type=str,
        default="/shared/storage",
        help="Storage root path"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without executing"
    )
    args = parser.parse_args()

    storage_path = Path(args.storage_path)
    compute_technicals(storage_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
