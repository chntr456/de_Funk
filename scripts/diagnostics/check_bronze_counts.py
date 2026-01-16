#!/usr/bin/env python3
"""
Bronze Layer Diagnostic - Check row counts and partition structure.

Usage:
    python -m scripts.diagnostics.check_bronze_counts --storage-root /shared/storage
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, countDistinct, min as spark_min, max as spark_max


def get_spark() -> SparkSession:
    """Get or create Spark session with Delta Lake support."""
    return (
        SparkSession.builder
        .appName("BronzeDiagnostics")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .getOrCreate()
    )


def check_table(spark: SparkSession, path: str, table_name: str) -> dict:
    """Check a bronze table and return stats."""
    result = {
        "table": table_name,
        "path": path,
        "exists": False,
        "row_count": 0,
        "columns": [],
        "partitions": [],
        "partition_counts": {},
        "snapshot_dates": [],
    }

    table_path = Path(path)
    if not table_path.exists():
        return result

    result["exists"] = True

    try:
        # Try Delta first, fall back to Parquet
        try:
            df = spark.read.format("delta").load(str(table_path))
            result["format"] = "delta"
        except Exception:
            df = spark.read.parquet(str(table_path))
            result["format"] = "parquet"

        result["row_count"] = df.count()
        result["columns"] = df.columns

        # Check for common partition columns
        partition_cols = []
        for col_name in ["snapshot_dt", "snapshot_date", "trade_date", "fiscal_date_ending", "report_type"]:
            if col_name in df.columns:
                partition_cols.append(col_name)

        result["partitions"] = partition_cols

        # Get partition value counts
        for pcol in partition_cols[:2]:  # Limit to first 2 partition columns
            try:
                counts = (
                    df.groupBy(pcol)
                    .agg(count("*").alias("cnt"))
                    .orderBy(col(pcol).desc())
                    .limit(20)
                    .collect()
                )
                result["partition_counts"][pcol] = [
                    {"value": str(row[pcol]), "count": row["cnt"]}
                    for row in counts
                ]
            except Exception as e:
                result["partition_counts"][pcol] = f"Error: {e}"

        # Check for snapshot_dt specifically
        if "snapshot_dt" in df.columns:
            snapshots = df.select("snapshot_dt").distinct().orderBy(col("snapshot_dt").desc()).limit(10).collect()
            result["snapshot_dates"] = [str(row["snapshot_dt"]) for row in snapshots]

        # Check for ticker count if applicable
        if "ticker" in df.columns:
            ticker_count = df.select("ticker").distinct().count()
            result["distinct_tickers"] = ticker_count

            # Sample tickers
            sample = df.select("ticker").distinct().limit(10).collect()
            result["sample_tickers"] = [row["ticker"] for row in sample]

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Check bronze layer row counts")
    parser.add_argument("--storage-root", default="/shared/storage", help="Storage root path")
    args = parser.parse_args()

    storage_root = Path(args.storage_root)
    bronze_root = storage_root / "bronze"

    print("=" * 70)
    print("  Bronze Layer Diagnostic Report")
    print("=" * 70)
    print(f"\nStorage root: {storage_root}")
    print(f"Bronze root: {bronze_root}")
    print()

    spark = get_spark()

    # Key tables to check
    tables = [
        # Alpha Vantage securities
        ("alpha_vantage/company_reference", "company_reference"),
        ("alpha_vantage/securities_reference", "securities_reference"),
        ("alpha_vantage/securities_prices_daily", "securities_prices_daily"),
        ("alpha_vantage/income_statements", "income_statements"),
        ("alpha_vantage/balance_sheets", "balance_sheets"),
        ("alpha_vantage/cash_flows", "cash_flows"),
        ("alpha_vantage/earnings", "earnings"),
        # Calendar
        ("calendar_seed", "calendar_seed"),
    ]

    for rel_path, name in tables:
        full_path = bronze_root / rel_path
        print(f"\n{'─' * 70}")
        print(f"Table: {name}")
        print(f"Path: {full_path}")
        print(f"{'─' * 70}")

        stats = check_table(spark, str(full_path), name)

        if not stats["exists"]:
            print("  ❌ NOT FOUND")
            continue

        print(f"  Format: {stats.get('format', 'unknown')}")
        print(f"  Row count: {stats['row_count']:,}")
        print(f"  Columns ({len(stats['columns'])}): {stats['columns'][:10]}{'...' if len(stats['columns']) > 10 else ''}")

        if stats.get("distinct_tickers"):
            print(f"  Distinct tickers: {stats['distinct_tickers']:,}")
            print(f"  Sample tickers: {stats.get('sample_tickers', [])[:5]}")

        if stats.get("snapshot_dates"):
            print(f"  Snapshot dates (latest 5): {stats['snapshot_dates'][:5]}")

        if stats.get("partition_counts"):
            print(f"  Partition analysis:")
            for pcol, counts in stats["partition_counts"].items():
                if isinstance(counts, str):
                    print(f"    {pcol}: {counts}")
                else:
                    print(f"    {pcol}:")
                    for item in counts[:5]:
                        print(f"      {item['value']}: {item['count']:,} rows")
                    if len(counts) > 5:
                        print(f"      ... and {len(counts) - 5} more")

        if stats.get("error"):
            print(f"  ⚠️ Error: {stats['error']}")

    # Check partition file structure
    print(f"\n{'=' * 70}")
    print("  Partition File Structure")
    print("=" * 70)

    for rel_path, name in [("alpha_vantage/company_reference", "company_reference")]:
        full_path = bronze_root / rel_path
        if full_path.exists():
            print(f"\n{name}:")
            # List partition directories
            try:
                subdirs = sorted([d.name for d in full_path.iterdir() if d.is_dir()])[:20]
                print(f"  Subdirectories ({len(subdirs)}): {subdirs[:10]}{'...' if len(subdirs) > 10 else ''}")

                # Count parquet files
                parquet_files = list(full_path.rglob("*.parquet"))
                print(f"  Parquet files: {len(parquet_files)}")

                # Check _delta_log
                delta_log = full_path / "_delta_log"
                if delta_log.exists():
                    log_files = list(delta_log.glob("*.json"))
                    print(f"  Delta log entries: {len(log_files)}")
            except Exception as e:
                print(f"  Error: {e}")

    spark.stop()
    print("\n✓ Diagnostic complete")


if __name__ == "__main__":
    main()
