#!/usr/bin/env python
"""
Compact Bronze Fundamentals - Fix file sprawl from ticker-based partitioning.

Problem: The original ingestion created 8,000+ × 2 = 16,000+ files per table
         due to partitioning by ticker/report_type.

Solution: This script reads all data and rewrites with partitioning configured
          in storage.json (single source of truth), reducing file count.

Usage:
    python -m scripts.maintenance.compact_bronze_fundamentals [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from datetime import date

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


TABLES_TO_COMPACT = [
    "income_statements",
    "balance_sheets",
    "cash_flows",
    "earnings",
]


def compact_table(spark, bronze_root: Path, table_name: str, storage_cfg: dict, dry_run: bool = False):
    """
    Compact a single table using partition config from storage.json.
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

    # Read all data (auto-detect Delta or Parquet)
    try:
        delta_log = table_path / "_delta_log"
        if delta_log.exists():
            df = spark.read.format("delta").load(str(table_path))
            print(f"     Format: Delta")
        else:
            df = spark.read.parquet(str(table_path))
            print(f"     Format: Parquet (will convert to Delta)")
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

    # Get partition config from storage.json (single source of truth)
    table_cfg = storage_cfg.get("tables", {}).get(table_name, {})
    partition_cols = table_cfg.get("partitions", [])

    # Validate partition columns exist
    for pcol in partition_cols:
        if pcol not in df.columns:
            print(f"     ✗ Missing partition column '{pcol}', cannot compact")
            return None

    # Write to temp location with new partitioning
    temp_path = bronze_root / f"{table_name}_compacted"

    try:
        # Coalesce to reduce files (4 files per partition)
        df = df.coalesce(4)

        # Write as Delta with partitioning from storage.json
        writer = df.write.format("delta").mode("overwrite")
        if partition_cols:
            print(f"     Partitions: {partition_cols} (from storage.json)")
            writer = writer.partitionBy(*partition_cols)
        else:
            print(f"     No partitions configured for {table_name} in storage.json")
        writer.save(str(temp_path))

        # Count files after
        new_files = list(temp_path.rglob("*.parquet"))
        print(f"     Files after: {len(new_files)}")
        print(f"     Reduction: {len(parquet_files)} → {len(new_files)}")
        print(f"     Output format: Delta")

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
    print("Solution: Rewrite with partitioning from storage.json (single source of truth)")
    print()

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print()

    # Initialize Spark with Delta Lake support
    try:
        from orchestration.common.spark_session import get_spark
        spark = get_spark("BronzeCompaction")
    except Exception as e:
        print(f"✗ Failed to create Spark session: {e}")
        return 1

    # Get bronze root and storage config (single source of truth for partitions)
    from config import ConfigLoader
    config = ConfigLoader().load()
    storage_cfg = config.storage
    bronze_root = Path(storage_cfg["roots"]["bronze"])

    print(f"Bronze root: {bronze_root}")
    print()

    # Determine tables to compact
    tables = [args.table] if args.table else TABLES_TO_COMPACT

    print(f"Tables to compact: {', '.join(tables)}")
    print("-" * 70)

    results = {}
    for table in tables:
        result = compact_table(spark, bronze_root, table, storage_cfg, dry_run=args.dry_run)
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
