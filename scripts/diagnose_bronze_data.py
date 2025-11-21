#!/usr/bin/env python3
"""Diagnose bronze data schema and compatibility."""

import sys
from pathlib import Path

# Add repo to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

import duckdb
from collections import defaultdict

def main():
    bronze_root = repo_root / "storage" / "bronze"

    print("=" * 80)
    print("BRONZE DATA DIAGNOSTICS")
    print("=" * 80)

    if not bronze_root.exists():
        print(f"\n❌ Bronze directory not found: {bronze_root}")
        print("\nYou need to run the ingestion pipeline to create bronze data.")
        return

    # Find all parquet files
    parquet_files = list(bronze_root.rglob("*.parquet"))

    if not parquet_files:
        print(f"\n❌ No parquet files found in {bronze_root}")
        return

    print(f"\n✓ Found {len(parquet_files)} parquet files")

    # Group by table
    by_table = defaultdict(list)
    for pf in parquet_files:
        rel_path = pf.relative_to(bronze_root)
        table = rel_path.parts[0]
        by_table[table].append(pf)

    print(f"\nBronze tables found: {list(by_table.keys())}")

    # Check each table schema
    conn = duckdb.connect()

    for table, files in sorted(by_table.items()):
        print(f"\n{'=' * 80}")
        print(f"TABLE: {table}")
        print(f"{'=' * 80}")
        print(f"Files: {len(files)}")
        print(f"Example: {files[0].relative_to(bronze_root)}")

        # Read schema
        try:
            # Use first file to get schema
            pattern = str(bronze_root / table / "**" / "*.parquet")
            df = conn.from_parquet(pattern, union_by_name=True)

            print(f"\nColumns ({len(df.columns)}):")
            for col in df.columns:
                print(f"  - {col}")

            # Get row count
            count = df.count('*').fetchone()[0]
            print(f"\nRows: {count:,}")

            # Show sample
            print(f"\nSample data:")
            sample = df.limit(3).df()
            print(sample.to_string())

            # Check for v2.0 columns
            print(f"\nV2.0 Compatibility Check:")
            v2_cols = ['asset_type', 'is_active', 'cik', 'primary_exchange']
            missing = [col for col in v2_cols if col not in df.columns]
            present = [col for col in v2_cols if col in df.columns]

            if present:
                print(f"  ✓ Has v2.0 columns: {present}")
            if missing:
                print(f"  ✗ Missing v2.0 columns: {missing}")

            # Detect data source
            if 'last_updated_utc' in df.columns or 'market' in df.columns:
                print(f"  📍 Detected: Polygon.io data (v1.x)")
            elif 'asset_type' in df.columns and 'is_active' in df.columns:
                print(f"  📍 Detected: Alpha Vantage data (v2.0)")
            else:
                print(f"  📍 Unknown data source")

        except Exception as e:
            print(f"\n❌ Error reading table: {e}")

    print(f"\n{'=' * 80}")
    print("RECOMMENDATIONS")
    print(f"{'=' * 80}")

    # Check if securities_reference exists
    if 'securities_reference' in by_table:
        df = conn.from_parquet(str(bronze_root / "securities_reference" / "**" / "*.parquet"))
        if 'asset_type' in df.columns:
            print("\n✓ You have v2.0 bronze data (securities_reference with asset_type)")
            print("  → Graph should work as-is")
        else:
            print("\n⚠ You have securities_reference but missing v2.0 columns")
            print("  → Need to re-run Alpha Vantage ingestion pipeline")
    else:
        print("\n⚠ No securities_reference table found")
        print("  → Current graph expects v2.0 Alpha Vantage data")
        print("  → Options:")
        print("     1. Run Alpha Vantage ingestion: python scripts/ingest_alpha_vantage.py")
        print("     2. Use legacy equity model instead of stocks model")

if __name__ == "__main__":
    main()
