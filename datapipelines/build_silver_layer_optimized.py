#!/usr/bin/env python3
"""
Build Silver Layer Script (Optimized for DuckDB).

Runs the CompanySilverBuilder with optimized storage layout:
- Consolidates to 1-5 large files (vs 100+ tiny files)
- Sorts by query columns (trade_date, ticker)
- No nested partitioning (flat structure)
- Result: 10-100x faster DuckDB queries

Usage:
    python scripts/build_silver_layer_optimized.py [--clear]

Options:
    --clear    Clear existing silver layer before rebuilding
"""

import argparse
from pathlib import Path
import sys
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.common.spark_session import get_spark
from models.builders.company_silver_builder import CompanySilverBuilder, load_config
from models.loaders.parquet_loader_optimized import ParquetLoaderOptimized


def clear_silver_layer(repo_root: Path):
    """Clear existing silver layer."""
    silver_path = repo_root / "storage" / "silver" / "company"
    if silver_path.exists():
        print(f"Clearing existing silver layer: {silver_path}")
        shutil.rmtree(silver_path)
        print("✓ Cleared")
    else:
        print("No existing silver layer found")


def main():
    parser = argparse.ArgumentParser(description="Build optimized Silver layer from Bronze")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing silver layer before rebuilding"
    )
    args = parser.parse_args()

    # Initialize
    repo_root = Path(__file__).parent.parent

    # Clear if requested
    if args.clear:
        clear_silver_layer(repo_root)
        print()

    # Create optimized Spark session for write performance
    print("Initializing Spark with optimized settings...")
    spark = get_spark("SilverLayerBuilder")

    # Optimize for large writes
    spark.conf.set("spark.sql.shuffle.partitions", "10")  # Reduce shuffle partitions
    spark.conf.set("spark.sql.files.maxPartitionBytes", "134217728")  # 128MB

    # Load configs
    storage_cfg, model_cfg = load_config(repo_root)

    # Build Silver layer with optimized loader
    print("\nBuilding Silver layer (optimized for DuckDB)...\n")
    print("=" * 60)

    builder = CompanySilverBuilder(spark, storage_cfg, model_cfg)

    # Replace loader with optimized version
    builder.loader = ParquetLoaderOptimized()

    # Build dimensions
    print("\n📦 Building Dimensions")
    print("-" * 60)

    print("\n🏢 dim_company")
    dim_company = builder.build_dim_company()
    dim_company.cache()
    print(f"  Rows: {dim_company.count():,}")

    print("\n🏛️  dim_exchange")
    dim_exchange = builder.build_dim_exchange()
    dim_exchange.cache()
    print(f"  Rows: {dim_exchange.count():,}")

    # Build facts
    print("\n\n📊 Building Facts")
    print("-" * 60)

    print("\n💰 fact_prices")
    fact_prices = builder.build_fact_prices()
    fact_prices.cache()
    print(f"  Rows: {fact_prices.count():,}")

    print("\n🔗 prices_with_company")
    prices_with_company = builder.build_prices_with_company(
        fact_prices,
        dim_company,
        dim_exchange,
    )
    prices_with_company.cache()
    print(f"  Rows: {prices_with_company.count():,}")

    # Write to Silver with optimizations
    print("\n\n💾 Writing to Silver Layer (Optimized)")
    print("=" * 60)

    print("\nWriting dim_company...")
    builder.loader.write_dim("dim_company", dim_company)

    print("\nWriting dim_exchange...")
    builder.loader.write_dim("dim_exchange", dim_exchange)

    print("\nWriting fact_prices...")
    builder.loader.write_fact(
        "fact_prices",
        fact_prices,
        sort_by=["trade_date", "ticker"]
    )

    print("\nWriting prices_with_company...")
    builder.loader.write_fact(
        "prices_with_company",
        prices_with_company,
        sort_by=["trade_date", "ticker"]
    )

    # Verify output
    print("\n\n✅ Silver Layer Build Complete!")
    print("=" * 60)

    silver_path = repo_root / "storage" / "silver" / "company"
    if silver_path.exists():
        import subprocess
        print("\nFile structure:")
        subprocess.run(["find", str(silver_path), "-name", "*.parquet", "-exec", "du", "-h", "{}", ";"])

        print("\nSummary:")
        result = subprocess.run(
            ["find", str(silver_path), "-name", "*.parquet"],
            capture_output=True,
            text=True
        )
        file_count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        print(f"  Total Parquet files: {file_count}")

        result = subprocess.run(["du", "-sh", str(silver_path)], capture_output=True, text=True)
        print(f"  Total size: {result.stdout.split()[0]}")

    # Unpersist cached data
    dim_company.unpersist()
    dim_exchange.unpersist()
    fact_prices.unpersist()
    prices_with_company.unpersist()

    spark.stop()

    print("\n🚀 Ready for fast DuckDB queries!")
    print("\nNext steps:")
    print("  1. Test queries: python test_duckdb_pipeline.py")
    print("  2. Run notebook app: python run_app.py")


if __name__ == "__main__":
    main()
