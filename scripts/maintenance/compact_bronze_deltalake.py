#!/usr/bin/env python
"""
Compact Bronze Delta Tables using delta-rs (Python library).

This script compacts small files in Delta Lake tables without requiring Spark.
Uses the deltalake Python library for OPTIMIZE operations.

Usage:
    # Dry run (show what would be compacted)
    python -m scripts.maintenance.compact_bronze_deltalake --dry-run

    # Compact all bronze tables
    python -m scripts.maintenance.compact_bronze_deltalake

    # Compact specific table
    python -m scripts.maintenance.compact_bronze_deltalake --table securities_prices_daily

    # Also vacuum old files
    python -m scripts.maintenance.compact_bronze_deltalake --vacuum
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


def get_table_stats(table_path: Path) -> dict:
    """Get statistics for a Delta table."""
    parquet_files = list(table_path.rglob('*.parquet'))
    total_size = sum(f.stat().st_size for f in parquet_files if f.exists())
    avg_size = total_size / len(parquet_files) / (1024 * 1024) if parquet_files else 0

    return {
        'file_count': len(parquet_files),
        'total_size_mb': total_size / (1024 * 1024),
        'avg_size_mb': avg_size,
        'has_delta_log': (table_path / '_delta_log').exists(),
    }


def compact_table(table_path: Path, dry_run: bool = False, vacuum: bool = False) -> dict:
    """
    Compact a Delta table using delta-rs.

    Args:
        table_path: Path to Delta table
        dry_run: If True, only show what would be done
        vacuum: If True, also vacuum old files

    Returns:
        Dictionary with compaction results
    """
    from deltalake import DeltaTable

    try:
        dt = DeltaTable(str(table_path))

        before_stats = get_table_stats(table_path)

        if dry_run:
            print(f"    [DRY RUN] Would compact {before_stats['file_count']} files")
            print(f"    [DRY RUN] Current avg size: {before_stats['avg_size_mb']:.2f} MB")
            return {'status': 'dry_run', 'before': before_stats}

        # Run compaction
        print(f"    Compacting {before_stats['file_count']} files...")
        optimize_result = dt.optimize.compact()
        print(f"    ✓ Compaction complete")

        # Optionally vacuum
        if vacuum:
            print(f"    Running vacuum...")
            dt.vacuum(retention_hours=168, enforce_retention_duration=True, dry_run=False)
            print(f"    ✓ Vacuum complete")

        after_stats = get_table_stats(table_path)

        return {
            'status': 'success',
            'before': before_stats,
            'after': after_stats,
            'files_removed': before_stats['file_count'] - after_stats['file_count'],
            'optimize_result': str(optimize_result),
        }

    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Compact Bronze Delta tables using delta-rs",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done')
    parser.add_argument('--table', type=str, help='Specific table to compact')
    parser.add_argument('--vacuum', action='store_true', help='Also vacuum old files')
    parser.add_argument('--layer', choices=['bronze', 'silver'], default='bronze', help='Layer to compact')

    args = parser.parse_args()

    print("=" * 70)
    print("DELTA LAKE COMPACTION (using delta-rs)")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Layer: {args.layer}")
    if args.dry_run:
        print("Mode: DRY RUN")
    print()

    # Check for deltalake
    try:
        from deltalake import DeltaTable
    except ImportError:
        print("ERROR: deltalake package not installed")
        print("Install with: pip install deltalake")
        sys.exit(1)

    # Find Delta tables
    layer_path = Path(repo_root) / "storage" / args.layer

    if not layer_path.exists():
        print(f"Layer path does not exist: {layer_path}")
        sys.exit(1)

    tables = []
    for table_dir in layer_path.iterdir():
        if table_dir.is_dir() and (table_dir / '_delta_log').exists():
            if args.table is None or table_dir.name == args.table:
                tables.append(table_dir)

    if not tables:
        if args.table:
            print(f"Table '{args.table}' not found or is not a Delta table")
        else:
            print("No Delta tables found")
        sys.exit(1)

    print(f"Found {len(tables)} Delta table(s) to process\n")

    results = []

    for table_path in sorted(tables):
        print(f"Table: {table_path.name}")

        stats = get_table_stats(table_path)
        print(f"  Files: {stats['file_count']}")
        print(f"  Size: {stats['total_size_mb']:.2f} MB")
        print(f"  Avg file: {stats['avg_size_mb']:.2f} MB")

        # Skip if already compacted (avg > 50 MB)
        if stats['avg_size_mb'] > 50 and not args.table:
            print(f"  ✓ Already well compacted, skipping")
            print()
            continue

        result = compact_table(table_path, dry_run=args.dry_run, vacuum=args.vacuum)
        results.append((table_path.name, result))

        if result['status'] == 'success':
            print(f"  Before: {result['before']['file_count']} files, {result['before']['avg_size_mb']:.2f} MB avg")
            print(f"  After: {result['after']['file_count']} files, {result['after']['avg_size_mb']:.2f} MB avg")
            print(f"  Files reduced: {result['files_removed']}")
        elif result['status'] == 'error':
            print(f"  ✗ Error: {result['error']}")

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if args.dry_run:
        print("DRY RUN - no changes made")
    else:
        successful = [r for _, r in results if r['status'] == 'success']
        errors = [r for _, r in results if r['status'] == 'error']

        total_files_removed = sum(r['files_removed'] for r in successful)

        print(f"Tables processed: {len(results)}")
        print(f"Successful: {len(successful)}")
        print(f"Errors: {len(errors)}")
        print(f"Total files removed: {total_files_removed}")

    print()


if __name__ == "__main__":
    main()
