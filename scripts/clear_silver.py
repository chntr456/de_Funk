#!/usr/bin/env python3
"""
Clear Silver Layer Utility

Removes all Silver parquet files and metadata for clean prototyping.
Bronze data is preserved.

Usage:
    # Clear all Silver data
    python scripts/clear_silver.py

    # Clear specific model
    python scripts/clear_silver.py --model equity

    # Dry run (show what would be deleted)
    python scripts/clear_silver.py --dry-run
"""

import argparse
import shutil
from pathlib import Path
import sys


def clear_silver(model: str = None, dry_run: bool = False):
    """
    Clear Silver layer data.

    Args:
        model: Specific model to clear (e.g., 'equity', 'corporate'). If None, clears all.
        dry_run: If True, only show what would be deleted without actually deleting
    """
    repo_root = Path(__file__).parent.parent
    silver_root = repo_root / "storage" / "silver"

    if not silver_root.exists():
        print(f"✓ Silver directory does not exist: {silver_root}")
        return

    # Determine what to delete
    if model:
        targets = [silver_root / model]
        title = f"Silver data for '{model}' model"
    else:
        # Get all subdirectories in silver (each is a model)
        targets = [d for d in silver_root.iterdir() if d.is_dir() and not d.name.startswith('_')]
        title = "ALL Silver data"

    if not targets:
        print(f"✓ No Silver data found to clear")
        return

    # Show what will be deleted
    print("=" * 80)
    print(f"Clear Silver Layer - {title}")
    print("=" * 80)
    print()

    total_size = 0
    file_count = 0

    for target in targets:
        if not target.exists():
            continue

        # Count files and size
        for item in target.rglob('*'):
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size

        print(f"  📁 {target.relative_to(repo_root)}")

        # Show subdirectories
        if target.is_dir():
            for subdir in sorted(target.iterdir()):
                if subdir.is_dir():
                    count = len(list(subdir.rglob('*.parquet')))
                    if count > 0:
                        print(f"      ├── {subdir.name}/ ({count} parquet files)")

    print()
    print(f"Total: {file_count} files, {total_size / (1024*1024):.1f} MB")
    print()

    if dry_run:
        print("🔍 DRY RUN - No files deleted")
        print("   Run without --dry-run to actually delete")
        return

    # Confirm deletion
    if not model:  # Extra confirmation for deleting all
        response = input("⚠️  Delete ALL Silver data? This cannot be undone! (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return
    else:
        response = input(f"Delete Silver data for '{model}'? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    # Delete
    deleted_count = 0
    for target in targets:
        if target.exists():
            print(f"  🗑️  Deleting {target.relative_to(repo_root)}...")
            shutil.rmtree(target)
            deleted_count += 1

    print()
    print(f"✅ Cleared {deleted_count} model(s) from Silver layer")
    print()
    print("Next steps:")
    print("  1. Rebuild Silver: python scripts/build_all_models.py --models equity")
    print("  2. Or specific model: python scripts/build_equity_silver.py")


def main():
    parser = argparse.ArgumentParser(
        description='Clear Silver layer for clean prototyping',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clear all Silver data
  python scripts/clear_silver.py

  # Clear only equity model
  python scripts/clear_silver.py --model equity

  # See what would be deleted without deleting
  python scripts/clear_silver.py --dry-run
        """
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Specific model to clear (e.g., equity, corporate). If not specified, clears all.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )

    args = parser.parse_args()

    clear_silver(model=args.model, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
