#!/usr/bin/env python
"""
Migrate Parquet to Delta Lake - Convert existing Parquet tables to Delta format.

This script converts all Bronze and Silver layer Parquet tables to Delta Lake format.
After migration, all new writes will use Delta Lake, providing:
- ACID transactions
- Time travel / version history
- Schema evolution
- Efficient upserts

Usage:
    python -m scripts.maintenance.migrate_parquet_to_delta [--dry-run] [--layer bronze|silver|all]

Examples:
    # Preview what would be migrated
    python -m scripts.maintenance.migrate_parquet_to_delta --dry-run

    # Migrate only bronze layer
    python -m scripts.maintenance.migrate_parquet_to_delta --layer bronze

    # Migrate everything
    python -m scripts.maintenance.migrate_parquet_to_delta --layer all
"""
from __future__ import annotations

import argparse
import shutil
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def find_parquet_tables(root_path: Path) -> List[Path]:
    """
    Find all Parquet tables (directories with .parquet files but no _delta_log).

    Args:
        root_path: Root directory to search

    Returns:
        List of paths to Parquet table directories
    """
    parquet_tables = []

    if not root_path.exists():
        return parquet_tables

    # Walk through directory structure
    for path in root_path.rglob("*.parquet"):
        table_dir = path.parent

        # Skip if already a Delta table
        if (table_dir / "_delta_log").exists():
            continue

        # Skip Hive partition directories (e.g., year=2024)
        # We want the root table directory, not partition subdirectories
        while table_dir.name and "=" in table_dir.name:
            table_dir = table_dir.parent

        # Add unique table directories
        if table_dir not in parquet_tables and table_dir.exists():
            parquet_tables.append(table_dir)

    return list(set(parquet_tables))


def is_delta_table(path: Path) -> bool:
    """Check if path is already a Delta Lake table."""
    return (path / "_delta_log").exists()


def migrate_table_spark(spark, source_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Migrate a single Parquet table to Delta format using Spark.

    Args:
        spark: SparkSession
        source_path: Path to Parquet table
        dry_run: If True, don't actually migrate

    Returns:
        Tuple of (success, message)
    """
    if dry_run:
        return True, f"[DRY RUN] Would migrate: {source_path}"

    try:
        # Read Parquet data
        print(f"  Reading Parquet from {source_path}...")
        df = spark.read.option("mergeSchema", "true").parquet(str(source_path))
        row_count = df.count()
        print(f"  Rows: {row_count:,}")

        if row_count == 0:
            return True, f"Skipped (empty table): {source_path}"

        # Create backup
        backup_path = source_path.parent / f"{source_path.name}_parquet_backup"
        print(f"  Creating backup at {backup_path}...")
        shutil.move(str(source_path), str(backup_path))

        # Write as Delta
        print(f"  Writing Delta to {source_path}...")
        df.write.format("delta").mode("overwrite").save(str(source_path))

        # Verify Delta table
        if is_delta_table(source_path):
            # Remove backup on success
            shutil.rmtree(backup_path)
            return True, f"Migrated: {source_path} ({row_count:,} rows)"
        else:
            # Restore backup on failure
            shutil.rmtree(source_path)
            shutil.move(str(backup_path), str(source_path))
            return False, f"Failed to create Delta table: {source_path}"

    except Exception as e:
        # Restore backup if it exists
        backup_path = source_path.parent / f"{source_path.name}_parquet_backup"
        if backup_path.exists() and not source_path.exists():
            shutil.move(str(backup_path), str(source_path))
        return False, f"Error migrating {source_path}: {e}"


def migrate_table_deltalake(source_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Migrate a single Parquet table to Delta format using delta-rs (no Spark needed).

    Args:
        source_path: Path to Parquet table
        dry_run: If True, don't actually migrate

    Returns:
        Tuple of (success, message)
    """
    try:
        from deltalake import write_deltalake
        import pyarrow.parquet as pq
    except ImportError:
        return False, "delta-rs not installed. Run: pip install deltalake"

    if dry_run:
        return True, f"[DRY RUN] Would migrate: {source_path}"

    try:
        # Read Parquet data
        print(f"  Reading Parquet from {source_path}...")

        # Handle partitioned tables
        parquet_files = list(source_path.rglob("*.parquet"))
        if not parquet_files:
            return True, f"Skipped (no parquet files): {source_path}"

        # Read all partitions using PyArrow
        table = pq.read_table(str(source_path))
        row_count = table.num_rows
        print(f"  Rows: {row_count:,}")

        if row_count == 0:
            return True, f"Skipped (empty table): {source_path}"

        # Create backup
        backup_path = source_path.parent / f"{source_path.name}_parquet_backup"
        print(f"  Creating backup at {backup_path}...")
        shutil.move(str(source_path), str(backup_path))

        # Write as Delta
        print(f"  Writing Delta to {source_path}...")
        write_deltalake(str(source_path), table, mode="overwrite")

        # Verify Delta table
        if is_delta_table(source_path):
            # Remove backup on success
            shutil.rmtree(backup_path)
            return True, f"Migrated: {source_path} ({row_count:,} rows)"
        else:
            # Restore backup on failure
            shutil.rmtree(source_path)
            shutil.move(str(backup_path), str(source_path))
            return False, f"Failed to create Delta table: {source_path}"

    except Exception as e:
        # Restore backup if it exists
        backup_path = source_path.parent / f"{source_path.name}_parquet_backup"
        if backup_path.exists() and not source_path.exists():
            shutil.move(str(backup_path), str(source_path))
        return False, f"Error migrating {source_path}: {e}"


def main():
    """Main entry point."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Migrate Parquet tables to Delta Lake format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes"
    )
    parser.add_argument(
        "--layer",
        choices=["bronze", "silver", "all"],
        default="all",
        help="Which layer to migrate (default: all)"
    )
    parser.add_argument(
        "--use-spark",
        action="store_true",
        help="Use Spark for migration (default: use delta-rs for faster migration)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("PARQUET TO DELTA LAKE MIGRATION")
    print("=" * 70)
    print()
    print(f"Repository root: {repo_root}")
    print(f"Layer: {args.layer}")
    print(f"Dry run: {args.dry_run}")
    print(f"Using: {'Spark' if args.use_spark else 'delta-rs (faster)'}")
    print()

    # Load storage config
    storage_path = repo_root / "configs" / "storage.json"
    with open(storage_path) as f:
        storage_cfg = json.load(f)

    # Determine paths to migrate
    paths_to_scan = []

    if args.layer in ("bronze", "all"):
        bronze_root = repo_root / storage_cfg["roots"]["bronze"]
        paths_to_scan.append(("Bronze", bronze_root))

    if args.layer in ("silver", "all"):
        silver_root = repo_root / storage_cfg["roots"]["silver"]
        paths_to_scan.append(("Silver", silver_root))

    # Find all Parquet tables
    tables_to_migrate: List[Tuple[str, Path]] = []

    for layer_name, root_path in paths_to_scan:
        print(f"Scanning {layer_name} layer: {root_path}")
        parquet_tables = find_parquet_tables(root_path)
        for table_path in parquet_tables:
            tables_to_migrate.append((layer_name, table_path))
        print(f"  Found {len(parquet_tables)} Parquet tables")
    print()

    if not tables_to_migrate:
        print("No Parquet tables found to migrate!")
        print("All tables may already be in Delta format.")
        return 0

    print(f"Tables to migrate: {len(tables_to_migrate)}")
    print("-" * 70)

    # Initialize Spark if needed
    spark = None
    if args.use_spark and not args.dry_run:
        try:
            from pyspark.sql import SparkSession

            spark = SparkSession.builder \
                .appName("ParquetToDeltaMigration") \
                .config("spark.driver.memory", "8g") \
                .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
                .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
                .getOrCreate()

            print("✓ Spark session created with Delta Lake support")
        except Exception as e:
            print(f"✗ Failed to create Spark session: {e}")
            print("  Falling back to delta-rs")
            args.use_spark = False

    # Migrate tables
    results = {
        "success": [],
        "failed": [],
        "skipped": []
    }

    for layer_name, table_path in tables_to_migrate:
        print(f"\n[{layer_name}] {table_path.name}")

        if args.use_spark and spark:
            success, message = migrate_table_spark(spark, table_path, args.dry_run)
        else:
            success, message = migrate_table_deltalake(table_path, args.dry_run)

        if "Skipped" in message:
            results["skipped"].append((table_path, message))
            print(f"  ⚠ {message}")
        elif success:
            results["success"].append((table_path, message))
            print(f"  ✓ {message}")
        else:
            results["failed"].append((table_path, message))
            print(f"  ✗ {message}")

    # Cleanup
    if spark:
        spark.stop()

    # Print summary
    print()
    print("=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"Total tables found: {len(tables_to_migrate)}")
    print(f"Successfully migrated: {len(results['success'])}")
    print(f"Skipped (empty/already delta): {len(results['skipped'])}")
    print(f"Failed: {len(results['failed'])}")

    if results["failed"]:
        print()
        print("Failed tables:")
        for table_path, message in results["failed"]:
            print(f"  - {table_path}: {message}")
        return 1

    if args.dry_run:
        print()
        print("To apply migration, run without --dry-run")

    return 0


if __name__ == "__main__":
    sys.exit(main())
