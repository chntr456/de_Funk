#!/usr/bin/env python
"""
Delete legacy Parquet tables that failed Delta migration.

These are v1.x tables superseded by v2.0 architecture.
"""
import shutil
from pathlib import Path

LEGACY_TABLES = [
    "storage/bronze/news",
    "storage/bronze/prices_daily",
    "storage/silver/forecast/facts/forecast_price",
    "storage/silver/forecast/facts/forecast_metrics",
]

def main():
    repo_root = Path(__file__).parent.parent.parent
    
    print("Deleting legacy tables...")
    for rel_path in LEGACY_TABLES:
        path = repo_root / rel_path
        if path.exists():
            shutil.rmtree(path)
            print(f"  ✓ Deleted: {rel_path}")
        else:
            print(f"  - Not found: {rel_path}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
