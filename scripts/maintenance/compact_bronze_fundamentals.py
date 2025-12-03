#!/usr/bin/env python
"""
Compact Bronze Fundamentals - Fix file sprawl from ticker-based partitioning.

Problem: The original ingestion created 8,000+ × 2 = 16,000+ files per table
         due to partitioning by ticker/report_type.

Solution: This script reads all data and rewrites with report_type/snapshot_date
          partitioning, reducing to ~4-8 files per table.

Usage:
    python -m scripts.maintenance.compact_bronze_fundamentals [--dry-run]
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from datetime import date

from utils.repo import setup_repo_imports
setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


TABLES_TO_COMPACT = [
    "income_statements",
    "balance_sheets",
    "cash_flows",
    "earnings",
]


def compact_table(spark, bronze_root: Path, table_name: str, dry_run: bool = False):
    """
    Compact a single table from ticker partitioning to report_type/snapshot_date.
    """
    table_path = bronze_root / table_name

    if not table_path.exists():
        print(f"  ⚠ {table_name}: Directory not found, skipping")
        return None

    # Count files before
    parquet_files = list(table_path.rglob("*.parquet"))
    if not parquet_files:
        print(f"  ⚠ {table_name}: No parquet files found, skipping")
        return None

    print(f"  📁 {table_name}:")
    print(f"     Files before: {len(parquet_files)}")

    if dry_run:
        print(f"     [DRY RUN] Would read and rewrite with new partitioning")
        return None

    # Read all data
    try:
        df = spark.read.parquet(str(table_path))
        row_count = df.count()
        print(f"     Rows: {row_count:,}")

        if row_count == 0:
            print(f"     ⚠ No data, skipping")
            return None

    except Exception as e:
        print(f"     ✗ Failed to read: {e}")
        return None

    # Ensure required columns exist
    if "snapshot_date" not in df.columns:
        from pyspark.sql.functions import lit, current_date
        df = df.withColumn("snapshot_date", current_date())
        print(f"     Added snapshot_date column")

    if "report_type" not in df.columns:
        print(f"     ✗ Missing report_type column, cannot compact")
        return None

    # Write to temp location with new partitioning
    temp_path = bronze_root / f"{table_name}_compacted"

    try:
        # Coalesce to reduce files (4 files per partition)
        df = df.coalesce(4)

        # Write with new partitioning
        df.write.mode("overwrite").partitionBy("report_type", "snapshot_date").parquet(str(temp_path))

        # Count files after
        new_files = list(temp_path.rglob("*.parquet"))
        print(f"     Files after: {len(new_files)}")
        print(f"     Reduction: {len(parquet_files)} → {len(new_files)} ({100 * (1 - len(new_files)/len(parquet_files)):.1f}% less)")

    except Exception as e:
        print(f"     ✗ Failed to write: {e}")
        if temp_path.exists():
            shutil.rmtree(temp_path)
        return None

    # Swap directories
    backup_path = bronze_root / f"{table_name}_old"
    try:
        # Move old to backup
        shutil.move(str(table_path), str(backup_path))
        # Move new to original location
        shutil.move(str(temp_path), str(table_path))
        # Delete backup
        shutil.rmtree(backup_path)
        print(f"     ✓ Compaction complete")
        return len(new_files)

    except Exception as e:
        print(f"     ✗ Failed to swap directories: {e}")
        # Try to restore
        if backup_path.exists() and not table_path.exists():
            shutil.move(str(backup_path), str(table_path))
        return None


def main():
    """Main entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--table", type=str, help="Compact specific table only")
    args = parser.parse_args()

    print("=" * 70)
    print("BRONZE FUNDAMENTALS COMPACTION")
    print("=" * 70)
    print()
    print("Problem: Ticker-based partitioning created 16,000+ files per table")
    print("Solution: Rewrite with report_type/snapshot_date partitioning")
    print()

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()

    # Initialize Spark
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder \
            .appName("BronzeCompaction") \
            .config("spark.driver.memory", "8g") \
            .config("spark.sql.parquet.compression.codec", "snappy") \
            .getOrCreate()
    except Exception as e:
        print(f"✗ Failed to create Spark session: {e}")
        return 1

    # Get bronze root
    from config import ConfigLoader
    config = ConfigLoader().load()
    bronze_root = Path(config.storage.get("roots", {}).get("bronze", "storage/bronze"))

    print(f"Bronze root: {bronze_root}")
    print()

    # Determine tables to compact
    tables = [args.table] if args.table else TABLES_TO_COMPACT

    print(f"Tables to compact: {', '.join(tables)}")
    print("-" * 70)

    results = {}
    for table in tables:
        result = compact_table(spark, bronze_root, table, dry_run=args.dry_run)
        results[table] = result

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    for table, file_count in results.items():
        if file_count is None:
            print(f"  {table}: Skipped or failed")
        else:
            print(f"  {table}: ✓ Compacted to {file_count} files")

    if args.dry_run:
        print()
        print("To apply changes, run without --dry-run")

    spark.stop()
    return 0


if __name__ == "__main__":
    exit(main())
