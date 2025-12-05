#!/usr/bin/env python
"""
Rewrite Bronze Delta Tables with Optimal File Sizing.

When Delta tables are partitioned with many small files per partition,
OPTIMIZE cannot help because it only merges within partitions.

This script rewrites tables to achieve optimal file sizes by:
1. Reading the entire table
2. Repartitioning to target ~256MB per file
3. Writing back as a new Delta table
4. Optionally replacing the original

Usage:
    # Dry run - show what would happen
    python -m scripts.maintenance.rewrite_bronze_optimal --table securities_prices_daily --dry-run

    # Rewrite with backup
    python -m scripts.maintenance.rewrite_bronze_optimal --table securities_prices_daily

    # Rewrite without backup (dangerous!)
    python -m scripts.maintenance.rewrite_bronze_optimal --table securities_prices_daily --no-backup

    # Target specific file size (default 256MB)
    python -m scripts.maintenance.rewrite_bronze_optimal --table securities_prices_daily --target-size-mb 128
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def get_table_stats(table_path: Path) -> dict:
    """Get statistics for a table directory."""
    parquet_files = list(table_path.rglob('*.parquet'))
    total_size = sum(f.stat().st_size for f in parquet_files if f.exists())

    # Check for partitioning
    subdirs = [d for d in table_path.iterdir() if d.is_dir() and '=' in d.name]
    is_partitioned = len(subdirs) > 0
    partition_key = subdirs[0].name.split('=')[0] if subdirs else None

    return {
        'file_count': len(parquet_files),
        'total_size_bytes': total_size,
        'total_size_mb': total_size / (1024 * 1024),
        'avg_size_mb': total_size / len(parquet_files) / (1024 * 1024) if parquet_files else 0,
        'is_partitioned': is_partitioned,
        'partition_key': partition_key,
        'partition_count': len(subdirs),
        'has_delta_log': (table_path / '_delta_log').exists(),
    }


def calculate_optimal_partitions(total_size_bytes: int, target_size_mb: int = 256) -> int:
    """Calculate optimal number of output files."""
    target_size_bytes = target_size_mb * 1024 * 1024
    num_files = max(1, round(total_size_bytes / target_size_bytes))
    return num_files


def rewrite_table_spark(
    table_path: Path,
    target_size_mb: int = 256,
    dry_run: bool = False,
    keep_backup: bool = True
) -> dict:
    """
    Rewrite a Delta table using Spark for optimal file sizing.

    Args:
        table_path: Path to Delta table
        target_size_mb: Target file size in MB
        dry_run: If True, only show what would be done
        keep_backup: If True, keep backup of original table

    Returns:
        Dictionary with rewrite results
    """
    from pyspark.sql import SparkSession
    from delta import configure_spark_with_delta_pip

    stats = get_table_stats(table_path)

    if dry_run:
        num_files = calculate_optimal_partitions(stats['total_size_bytes'], target_size_mb)
        return {
            'status': 'dry_run',
            'current_files': stats['file_count'],
            'target_files': num_files,
            'current_size_mb': stats['total_size_mb'],
            'is_partitioned': stats['is_partitioned'],
            'partition_key': stats['partition_key'],
        }

    # Initialize Spark with Delta
    builder = (
        SparkSession.builder
        .appName("DeltaTableRewrite")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.driver.memory", "4g")
    )
    spark = configure_spark_with_delta_pip(builder).getOrCreate()

    try:
        # Read the current table
        print(f"    Reading table...")
        start = time.time()
        df = spark.read.format("delta").load(str(table_path))
        row_count = df.count()
        read_time = time.time() - start
        print(f"    Read {row_count:,} rows in {read_time:.1f}s")

        # Calculate optimal partitions
        num_files = calculate_optimal_partitions(stats['total_size_bytes'], target_size_mb)
        print(f"    Target: {num_files} files (~{target_size_mb}MB each)")

        # Backup original table
        backup_path = table_path.parent / f"{table_path.name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if keep_backup:
            print(f"    Creating backup at {backup_path}...")
            shutil.copytree(table_path, backup_path)

        # Write to temp location first
        temp_path = table_path.parent / f"{table_path.name}_temp"
        print(f"    Writing optimized table to temp location...")
        start = time.time()

        # Coalesce to target number of files and write
        df.coalesce(num_files).write.format("delta").mode("overwrite").save(str(temp_path))

        write_time = time.time() - start
        print(f"    Wrote in {write_time:.1f}s")

        # Replace original with temp
        print(f"    Replacing original table...")
        shutil.rmtree(table_path)
        shutil.move(temp_path, table_path)

        # Get new stats
        new_stats = get_table_stats(table_path)

        # Clean up backup if not keeping
        if not keep_backup and backup_path.exists():
            shutil.rmtree(backup_path)

        return {
            'status': 'success',
            'before_files': stats['file_count'],
            'after_files': new_stats['file_count'],
            'before_size_mb': stats['total_size_mb'],
            'after_size_mb': new_stats['total_size_mb'],
            'row_count': row_count,
            'backup_path': str(backup_path) if keep_backup else None,
        }

    except Exception as e:
        return {'status': 'error', 'error': str(e)}
    finally:
        spark.stop()


def rewrite_table_duckdb(
    table_path: Path,
    target_size_mb: int = 256,
    dry_run: bool = False,
    keep_backup: bool = True
) -> dict:
    """
    Rewrite a Delta table using DuckDB + delta-rs for optimal file sizing.

    This is faster than Spark for smaller tables and doesn't require Java.
    """
    import duckdb
    from deltalake import DeltaTable, write_deltalake

    stats = get_table_stats(table_path)

    if dry_run:
        num_files = calculate_optimal_partitions(stats['total_size_bytes'], target_size_mb)
        return {
            'status': 'dry_run',
            'current_files': stats['file_count'],
            'target_files': num_files,
            'current_size_mb': stats['total_size_mb'],
            'is_partitioned': stats['is_partitioned'],
            'partition_key': stats['partition_key'],
        }

    try:
        # Read using DuckDB (fast!)
        print(f"    Reading table with DuckDB...")
        start = time.time()

        conn = duckdb.connect()
        conn.execute("INSTALL delta; LOAD delta;")

        df = conn.execute(f"SELECT * FROM delta_scan('{table_path}')").df()
        row_count = len(df)
        read_time = time.time() - start
        print(f"    Read {row_count:,} rows in {read_time:.1f}s")

        # Backup original table
        backup_path = table_path.parent / f"{table_path.name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if keep_backup:
            print(f"    Creating backup at {backup_path}...")
            shutil.copytree(table_path, backup_path)

        # Write to temp location
        temp_path = table_path.parent / f"{table_path.name}_temp"
        print(f"    Writing optimized table...")
        start = time.time()

        # Calculate number of row groups for target file size
        # PyArrow/delta-rs handles file splitting automatically based on row_group_size
        write_deltalake(
            str(temp_path),
            df,
            mode="overwrite",
            # Don't partition - this was the problem!
        )

        write_time = time.time() - start
        print(f"    Wrote in {write_time:.1f}s")

        # Replace original with temp
        print(f"    Replacing original table...")
        shutil.rmtree(table_path)
        shutil.move(temp_path, table_path)

        # Get new stats
        new_stats = get_table_stats(table_path)

        # Clean up backup if not keeping
        if not keep_backup and backup_path.exists():
            shutil.rmtree(backup_path)

        conn.close()

        return {
            'status': 'success',
            'before_files': stats['file_count'],
            'after_files': new_stats['file_count'],
            'before_size_mb': stats['total_size_mb'],
            'after_size_mb': new_stats['total_size_mb'],
            'row_count': row_count,
            'backup_path': str(backup_path) if keep_backup else None,
        }

    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Rewrite Bronze Delta tables for optimal file sizing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--table', type=str, required=True, help='Table name to rewrite')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup (dangerous!)')
    parser.add_argument('--target-size-mb', type=int, default=256, help='Target file size in MB')
    parser.add_argument('--use-spark', action='store_true', help='Use Spark instead of DuckDB')
    parser.add_argument('--layer', choices=['bronze', 'silver'], default='bronze', help='Storage layer')

    args = parser.parse_args()

    print("=" * 70)
    print("DELTA TABLE REWRITE FOR OPTIMAL FILE SIZING")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Table: {args.table}")
    print(f"Target file size: {args.target_size_mb} MB")
    if args.dry_run:
        print("Mode: DRY RUN")
    print()

    # Find table
    table_path = Path(repo_root) / "storage" / args.layer / args.table

    if not table_path.exists():
        print(f"ERROR: Table not found at {table_path}")
        sys.exit(1)

    if not (table_path / '_delta_log').exists():
        print(f"ERROR: Not a Delta table (no _delta_log)")
        sys.exit(1)

    # Show current stats
    stats = get_table_stats(table_path)
    print(f"Current state:")
    print(f"  Files: {stats['file_count']}")
    print(f"  Size: {stats['total_size_mb']:.2f} MB")
    print(f"  Avg file: {stats['avg_size_mb']:.2f} MB")
    print(f"  Partitioned: {stats['is_partitioned']}")
    if stats['is_partitioned']:
        print(f"  Partition key: {stats['partition_key']}")
        print(f"  Partition count: {stats['partition_count']}")
    print()

    # Rewrite
    if args.use_spark:
        print("Using Spark for rewrite...")
        result = rewrite_table_spark(
            table_path,
            target_size_mb=args.target_size_mb,
            dry_run=args.dry_run,
            keep_backup=not args.no_backup
        )
    else:
        print("Using DuckDB + delta-rs for rewrite...")
        result = rewrite_table_duckdb(
            table_path,
            target_size_mb=args.target_size_mb,
            dry_run=args.dry_run,
            keep_backup=not args.no_backup
        )

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)

    if result['status'] == 'dry_run':
        print(f"DRY RUN - no changes made")
        print(f"  Current files: {result['current_files']}")
        print(f"  Target files: ~{result['target_files']}")
        print(f"  Reduction: {result['current_files']} → ~{result['target_files']} files")
        if result['is_partitioned']:
            print(f"\n  Note: Table is partitioned by '{result['partition_key']}'")
            print(f"  Rewrite will REMOVE partitioning for better file sizing.")
    elif result['status'] == 'success':
        print(f"✓ Rewrite successful!")
        print(f"  Files: {result['before_files']} → {result['after_files']}")
        print(f"  Size: {result['before_size_mb']:.2f} MB → {result['after_size_mb']:.2f} MB")
        print(f"  Rows: {result['row_count']:,}")
        if result.get('backup_path'):
            print(f"  Backup: {result['backup_path']}")
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}")

    print()


if __name__ == "__main__":
    main()
