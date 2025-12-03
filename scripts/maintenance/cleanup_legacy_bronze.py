#!/usr/bin/env python
"""
Cleanup Legacy Bronze Data - Remove v1.x tables superseded by v2.0 architecture.

These tables are marked as legacy in storage.json and have been replaced:
- ref_all_tickers -> securities_reference
- ref_ticker -> securities_reference  
- prices_daily -> securities_prices_daily (already deleted)
- news -> (already deleted)
- exchanges -> (keep - still used)

Usage:
    python -m scripts.maintenance.cleanup_legacy_bronze [--dry-run]
"""
import shutil
import argparse
from pathlib import Path

# Legacy tables to remove (superseded by v2.0)
LEGACY_TABLES = [
    "storage/bronze/ref_all_tickers",
    "storage/bronze/ref_ticker",
    # These were already deleted in previous cleanup:
    # "storage/bronze/news",
    # "storage/bronze/prices_daily",
]

def main():
    parser = argparse.ArgumentParser(description="Remove legacy v1.x bronze tables")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent.parent
    
    print("=" * 60)
    print("CLEANUP LEGACY BRONZE DATA")
    print("=" * 60)
    print(f"Dry run: {args.dry_run}")
    print()
    
    deleted = 0
    for rel_path in LEGACY_TABLES:
        path = repo_root / rel_path
        if path.exists():
            if args.dry_run:
                # Count files/size
                files = list(path.rglob("*"))
                size = sum(f.stat().st_size for f in files if f.is_file())
                print(f"  [DRY RUN] Would delete: {rel_path}")
                print(f"            Files: {len(files)}, Size: {size / 1024 / 1024:.1f} MB")
            else:
                shutil.rmtree(path)
                print(f"  ✓ Deleted: {rel_path}")
                deleted += 1
        else:
            print(f"  - Already gone: {rel_path}")
    
    print()
    if args.dry_run:
        print("Run without --dry-run to delete these tables.")
    else:
        print(f"Deleted {deleted} legacy tables.")

if __name__ == "__main__":
    main()
