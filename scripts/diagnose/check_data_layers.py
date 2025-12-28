#!/usr/bin/env python3
"""
Diagnose Bronze and Silver data layers.

Scans storage directories and reports on table contents.

Usage:
    python -m scripts.diagnose.check_data_layers
    python -m scripts.diagnose.check_data_layers --storage-path /shared/storage
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
import argparse

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.repo import setup_repo_imports
setup_repo_imports()


def check_parquet_table(spark, path: Path, name: str) -> dict:
    """Check a parquet table and return stats."""
    result = {"name": name, "path": str(path), "exists": False, "rows": 0, "columns": [], "error": None}

    if not path.exists():
        return result

    # Check for parquet files
    parquet_files = list(path.glob("*.parquet")) + list(path.glob("**/*.parquet"))
    if not parquet_files:
        result["error"] = "No parquet files found"
        return result

    result["exists"] = True

    try:
        df = spark.read.parquet(str(path))
        result["rows"] = df.count()
        result["columns"] = df.columns
    except Exception as e:
        result["error"] = str(e)

    return result


def scan_directory(spark, base_path: Path, layer_name: str) -> list:
    """Scan a directory for tables."""
    results = []

    if not base_path.exists():
        print(f"  ⚠ {layer_name} path does not exist: {base_path}")
        return results

    # Look for tables (directories with parquet files)
    for item in sorted(base_path.iterdir()):
        if item.is_dir():
            # Check if it's a table (has parquet files)
            has_parquet = bool(list(item.glob("*.parquet")) or list(item.glob("**/*.parquet")))

            if has_parquet:
                result = check_parquet_table(spark, item, item.name)
                results.append(result)
            else:
                # Recurse into subdirectory
                for subitem in sorted(item.iterdir()):
                    if subitem.is_dir():
                        has_parquet = bool(list(subitem.glob("*.parquet")) or list(subitem.glob("**/*.parquet")))
                        if has_parquet:
                            result = check_parquet_table(spark, subitem, f"{item.name}/{subitem.name}")
                            results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Diagnose Bronze and Silver data layers")
    parser.add_argument("--storage-path", default="/shared/storage", help="Base storage path")
    parser.add_argument("--bronze-only", action="store_true", help="Only check Bronze layer")
    parser.add_argument("--silver-only", action="store_true", help="Only check Silver layer")
    args = parser.parse_args()

    storage_path = Path(args.storage_path)

    print("=" * 70)
    print("DATA LAYER DIAGNOSTIC")
    print("=" * 70)
    print(f"Storage path: {storage_path}")
    print()

    # Initialize Spark
    print("Initializing Spark...")
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName("DataDiagnostic").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    print()

    # Check what directories exist at top level
    print("=" * 70)
    print("STORAGE STRUCTURE")
    print("=" * 70)
    if storage_path.exists():
        for item in sorted(storage_path.iterdir()):
            if item.is_dir():
                print(f"  📁 {item.name}/")
    else:
        print(f"  ⚠ Storage path does not exist: {storage_path}")
    print()

    # Check Bronze layer
    if not args.silver_only:
        print("=" * 70)
        print("BRONZE LAYER")
        print("=" * 70)
        bronze_path = storage_path / "bronze"
        bronze_tables = scan_directory(spark, bronze_path, "Bronze")

        if bronze_tables:
            total_rows = 0
            for t in bronze_tables:
                status = "✓" if t["exists"] and not t["error"] else "✗"
                rows_str = f"{t['rows']:,}" if t["rows"] else "empty"
                if t["error"]:
                    print(f"  {status} {t['name']}: {t['error']}")
                else:
                    print(f"  {status} {t['name']}: {rows_str} rows")
                    total_rows += t["rows"]
            print(f"\n  Total Bronze rows: {total_rows:,}")
        else:
            print("  No tables found in Bronze layer")
        print()

    # Check Silver layer
    if not args.bronze_only:
        print("=" * 70)
        print("SILVER LAYER")
        print("=" * 70)
        silver_path = storage_path / "silver"

        # Check standard silver path
        silver_tables = scan_directory(spark, silver_path, "Silver")

        if silver_tables:
            total_rows = 0
            for t in silver_tables:
                status = "✓" if t["exists"] and not t["error"] else "✗"
                rows_str = f"{t['rows']:,}" if t["rows"] else "empty"
                if t["error"]:
                    print(f"  {status} {t['name']}: {t['error']}")
                else:
                    print(f"  {status} {t['name']}: {rows_str} rows")
                    total_rows += t["rows"]
            print(f"\n  Total Silver rows: {total_rows:,}")
        else:
            print("  No tables found in Silver layer")
        print()

        # Also check for misplaced Silver tables (directly under storage)
        print("=" * 70)
        print("CHECKING FOR MISPLACED TABLES")
        print("=" * 70)

        # Known model names that might be misplaced
        model_names = ["stocks", "company", "temporal", "forecast", "macro", "city_finance"]
        misplaced = []

        for model in model_names:
            model_path = storage_path / model
            if model_path.exists() and model_path.is_dir():
                tables = scan_directory(spark, model_path, model)
                if tables:
                    misplaced.append((model, tables))

        if misplaced:
            print("  ⚠ Found tables outside silver/ directory:")
            for model, tables in misplaced:
                print(f"\n  📁 {model}/ (should be silver/{model}/)")
                for t in tables:
                    rows_str = f"{t['rows']:,}" if t["rows"] else "empty"
                    print(f"      - {t['name']}: {rows_str} rows")
        else:
            print("  ✓ No misplaced tables found")
        print()

    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)

    spark.stop()


if __name__ == "__main__":
    main()
