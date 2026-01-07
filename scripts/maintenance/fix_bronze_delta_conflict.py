#!/usr/bin/env python3
"""
Fix Bronze Delta Lake Conflict

This script fixes the issue where Bronze tables have BOTH:
- Partitioned Parquet data (in partition directories like snapshot_dt=2025-12-03/)
- Stale Delta Lake data (in _delta_log/ with root-level parquet files)

The stale Delta data has fewer rows than the partitioned data, causing the
Silver build to only process a fraction of the available data.

Solution:
1. Read ALL data from partition directories (the complete data)
2. Remove stale Delta log and root-level parquet files
3. Write properly as Delta table

Usage:
    python -m scripts.maintenance.fix_bronze_delta_conflict --table securities_reference
    python -m scripts.maintenance.fix_bronze_delta_conflict --all
    python -m scripts.maintenance.fix_bronze_delta_conflict --table securities_reference --dry-run
"""
from __future__ import annotations

import sys
import os
import shutil
from pathlib import Path
import argparse

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger
from orchestration.common.spark_session import get_spark

logger = get_logger(__name__)

# Tables that might have this conflict
BRONZE_TABLES = [
    'securities_reference',
    'securities_prices_daily',
    'income_statements',
    'balance_sheets',
    'cash_flows',
    'earnings',
]


def analyze_table(spark, table_path: Path) -> dict:
    """Analyze a Bronze table for Delta/Parquet conflicts."""
    result = {
        'path': str(table_path),
        'has_delta_log': False,
        'has_partition_dirs': False,
        'has_root_parquet': False,
        'partition_dirs': [],
        'root_parquet_files': [],
        'delta_row_count': 0,
        'partition_row_count': 0,
        'needs_fix': False,
    }

    if not table_path.exists():
        logger.warning(f"Table path does not exist: {table_path}")
        return result

    # Check for Delta log
    delta_log = table_path / '_delta_log'
    result['has_delta_log'] = delta_log.exists()

    # Check for partition directories and root-level parquet files
    for item in table_path.iterdir():
        if item.is_dir():
            if item.name == '_delta_log':
                continue
            elif '=' in item.name:  # Partition directory like snapshot_dt=2025-12-03
                result['has_partition_dirs'] = True
                result['partition_dirs'].append(item.name)
        elif item.suffix == '.parquet':
            result['has_root_parquet'] = True
            result['root_parquet_files'].append(item.name)

    # If we have both Delta log AND partition directories, there's a conflict
    if result['has_delta_log'] and result['has_partition_dirs']:
        result['needs_fix'] = True

        # Count rows in Delta table
        try:
            delta_df = spark.read.format("delta").load(str(table_path))
            result['delta_row_count'] = delta_df.count()
        except Exception as e:
            logger.warning(f"Could not read Delta table: {e}")
            # Try reading as parquet (might just be the root files)
            try:
                root_files = [str(table_path / f) for f in result['root_parquet_files']]
                if root_files:
                    parquet_df = spark.read.parquet(*root_files)
                    result['delta_row_count'] = parquet_df.count()
            except Exception:
                pass

        # Count rows in partition directories
        try:
            partition_paths = [str(table_path / d) for d in result['partition_dirs']]
            partition_df = spark.read.parquet(*partition_paths)
            result['partition_row_count'] = partition_df.count()
        except Exception as e:
            logger.warning(f"Could not read partition data: {e}")

    return result


def fix_table(spark, table_path: Path, storage_cfg: dict, dry_run: bool = False) -> bool:
    """
    Fix a Bronze table by consolidating partitioned data into Delta.

    Steps:
    1. Read all data from partition directories
    2. Remove Delta log and root-level parquet files
    3. Write as proper Delta table (using partition config from storage.json)

    Args:
        spark: SparkSession
        table_path: Path to the table
        storage_cfg: Storage configuration dict (from storage.json)
        dry_run: If True, only show what would be done
    """
    logger.info(f"Fixing table: {table_path}")

    # Get partition directories
    partition_dirs = []
    delta_log = table_path / '_delta_log'
    root_parquet_files = []

    for item in table_path.iterdir():
        if item.is_dir():
            if item.name == '_delta_log':
                continue
            elif '=' in item.name:
                partition_dirs.append(item)
        elif item.suffix == '.parquet':
            root_parquet_files.append(item)

    if not partition_dirs:
        logger.warning(f"No partition directories found in {table_path}")
        return False

    logger.info(f"  Found {len(partition_dirs)} partition directories")
    logger.info(f"  Found {len(root_parquet_files)} root-level parquet files")

    # Read all partition data
    partition_paths = [str(p) for p in partition_dirs]
    logger.info(f"  Reading from partitions: {[p.name for p in partition_dirs]}")

    try:
        df = spark.read.option("basePath", str(table_path)).parquet(*partition_paths)
        row_count = df.count()
        logger.info(f"  Total rows in partitions: {row_count:,}")

        if row_count == 0:
            logger.warning("  No data in partitions, skipping")
            return False

        # Show schema
        logger.info(f"  Schema: {df.columns}")

    except Exception as e:
        logger.error(f"  Error reading partition data: {e}")
        return False

    if dry_run:
        logger.info(f"  [DRY RUN] Would remove Delta log and {len(root_parquet_files)} root parquet files")
        logger.info(f"  [DRY RUN] Would write {row_count:,} rows as Delta table")
        return True

    # Cache the data before removing files
    df = df.cache()
    _ = df.count()  # Force cache

    # Remove stale Delta log
    if delta_log.exists():
        logger.info(f"  Removing stale Delta log: {delta_log}")
        shutil.rmtree(delta_log)

    # Remove root-level parquet files
    for pf in root_parquet_files:
        logger.info(f"  Removing root parquet: {pf}")
        pf.unlink()

    # Also remove partition directories (we'll rewrite everything)
    for pd in partition_dirs:
        logger.info(f"  Removing partition directory: {pd}")
        shutil.rmtree(pd)

    # Write as Delta table
    logger.info(f"  Writing {row_count:,} rows as Delta table...")

    # Get partition columns from storage.json (single source of truth)
    table_name = table_path.name
    table_cfg = storage_cfg.get("tables", {}).get(table_name, {})
    partition_cols = table_cfg.get("partitions", [])

    writer = df.write.format("delta").mode("overwrite")
    if partition_cols:
        logger.info(f"  Partitioning by: {partition_cols} (from storage.json)")
        writer = writer.partitionBy(*partition_cols)
    else:
        logger.info(f"  No partitions configured for {table_name} in storage.json")

    writer.save(str(table_path))

    # Verify
    verify_df = spark.read.format("delta").load(str(table_path))
    verify_count = verify_df.count()
    logger.info(f"  ✓ Verified: {verify_count:,} rows in Delta table")

    # Uncache
    df.unpersist()

    return verify_count == row_count


def main():
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Fix Bronze Delta Lake conflicts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--table',
        type=str,
        help='Specific table to fix (e.g., securities_reference)'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Fix all Bronze tables'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Only analyze tables, do not fix'
    )

    args = parser.parse_args()

    if not args.table and not args.all:
        parser.print_help()
        print("\nError: Must specify --table or --all")
        sys.exit(1)

    # Initialize Spark
    logger.info("Initializing Spark...")
    spark = get_spark("BronzeDeltaFix")

    # Load storage config (single source of truth for partitions)
    import json
    storage_json_path = Path(repo_root) / "configs" / "storage.json"
    with open(storage_json_path) as f:
        storage_cfg = json.load(f)
    logger.info(f"Loaded storage config from {storage_json_path}")

    bronze_root = Path(repo_root) / "storage" / "bronze"

    # Determine which tables to process
    if args.all:
        tables = BRONZE_TABLES
    else:
        tables = [args.table]

    print("\n" + "=" * 70)
    print("BRONZE DELTA CONFLICT ANALYSIS")
    print("=" * 70)

    results = {}
    for table_name in tables:
        table_path = bronze_root / table_name
        if not table_path.exists():
            logger.info(f"Skipping {table_name} (does not exist)")
            continue

        logger.info(f"\nAnalyzing {table_name}...")
        result = analyze_table(spark, table_path)
        results[table_name] = result

        print(f"\n{table_name}:")
        print(f"  Path: {result['path']}")
        print(f"  Has Delta log: {result['has_delta_log']}")
        print(f"  Has partition dirs: {result['has_partition_dirs']}")
        print(f"  Partition dirs: {result['partition_dirs']}")
        print(f"  Root parquet files: {len(result['root_parquet_files'])}")

        if result['needs_fix']:
            print(f"  ⚠️  CONFLICT DETECTED")
            print(f"     Delta rows: {result['delta_row_count']:,}")
            print(f"     Partition rows: {result['partition_row_count']:,}")
            print(f"     Missing: {result['partition_row_count'] - result['delta_row_count']:,} rows")

    if args.analyze_only:
        print("\n" + "=" * 70)
        print("Analysis complete (--analyze-only mode)")
        print("=" * 70)
        spark.stop()
        return

    # Fix tables that need it
    tables_to_fix = [name for name, result in results.items() if result['needs_fix']]

    if not tables_to_fix:
        print("\n✓ No tables need fixing")
        spark.stop()
        return

    print("\n" + "=" * 70)
    print(f"FIXING {len(tables_to_fix)} TABLE(S)")
    if args.dry_run:
        print("[DRY RUN MODE]")
    print("=" * 70)

    for table_name in tables_to_fix:
        table_path = bronze_root / table_name
        success = fix_table(spark, table_path, storage_cfg, dry_run=args.dry_run)

        if success:
            print(f"✓ {table_name}: Fixed")
        else:
            print(f"✗ {table_name}: Failed")

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)

    if not args.dry_run:
        print("\nNext step: Re-run Silver build:")
        print("  python -m scripts.build.build_silver --models stocks company")

    spark.stop()


if __name__ == "__main__":
    main()
