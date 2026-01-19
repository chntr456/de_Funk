#!/usr/bin/env python3
"""
Test Delta reads from Bronze vs Silver to diagnose session issues.

Usage:
    python scripts/debug/test_delta_reads.py
"""
from pathlib import Path
import sys

# Setup imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from orchestration.common.spark_session import get_spark

def main():
    print("=" * 60)
    print("Delta Read Test: Bronze vs Silver")
    print("=" * 60)

    spark = get_spark(app_name="DeltaReadTest")
    print(f"\nSpark session created: {spark}")

    # Bronze path (works during temporal/stocks build)
    bronze_path = "/shared/storage/bronze/alpha_vantage/listing_status"
    print(f"\n--- BRONZE TEST ---")
    print(f"Path: {bronze_path}")
    print(f"Exists: {Path(bronze_path).exists()}")
    print(f"Is Delta: {(Path(bronze_path) / '_delta_log').exists()}")

    try:
        df_bronze = spark.read.format("delta").load(bronze_path)
        print(f"Read SUCCESS - count: {df_bronze.count()}")
    except Exception as e:
        print(f"Read FAILED: {e}")

    # Silver path (supposedly fails during forecast)
    silver_path = "/shared/storage/silver/stocks/dims/dim_stock"
    print(f"\n--- SILVER TEST ---")
    print(f"Path: {silver_path}")
    print(f"Exists: {Path(silver_path).exists()}")
    print(f"Is Delta: {(Path(silver_path) / '_delta_log').exists()}")

    try:
        df_silver = spark.read.format("delta").load(silver_path)
        print(f"Read SUCCESS - count: {df_silver.count()}")
    except Exception as e:
        print(f"Read FAILED: {e}")

    # List what's actually in silver/stocks
    print(f"\n--- SILVER DIRECTORY CONTENTS ---")
    silver_root = Path("/shared/storage/silver/stocks")
    if silver_root.exists():
        for item in silver_root.rglob("*"):
            if item.is_dir() and item.name == "_delta_log":
                print(f"  Delta table: {item.parent}")
    else:
        print(f"  Directory does not exist: {silver_root}")

    spark.stop()
    print("\nDone.")

if __name__ == "__main__":
    main()
