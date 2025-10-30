#!/usr/bin/env python3
"""
Standalone Storage Rebuild Script

Run this directly on your machine at:
/home/ms_trixie/PycharmProjects/de_Funk/

Usage:
    cd /home/ms_trixie/PycharmProjects/de_Funk
    python rebuild_storage_standalone.py
"""

import sys
from pathlib import Path

# Ensure we're in the right directory
repo_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(repo_root))

print("=" * 70)
print("Storage Layer Rebuild (Optimized for DuckDB)")
print("=" * 70)
print(f"\nWorking directory: {repo_root}")

# Check dependencies
print("\n1. Checking dependencies...")
try:
    import pyspark
    print("   ✓ pyspark installed")
except ImportError:
    print("   ✗ pyspark not installed")
    print("\n   Installing pyspark...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyspark", "-q"])
    print("   ✓ pyspark installed")

# Import after ensuring pyspark is available
from src.common.spark_session import get_spark
from src.model.silver.company_silver_builder import CompanySilverBuilder, load_config
from src.model.loaders.parquet_loader_optimized import ParquetLoaderOptimized

# Check storage
print("\n2. Checking storage...")
bronze_path = repo_root / "storage" / "bronze"
silver_path = repo_root / "storage" / "silver"

if not bronze_path.exists():
    print(f"   ✗ Bronze layer not found: {bronze_path}")
    print("   Please ensure bronze layer exists before rebuilding silver")
    sys.exit(1)

print(f"   ✓ Bronze layer found: {bronze_path}")

if silver_path.exists():
    print(f"   ⚠ Silver layer exists: {silver_path}")
    response = input("   Clear and rebuild? (yes/no): ").lower().strip()
    if response == 'yes':
        import shutil
        print("   Clearing silver layer...")
        shutil.rmtree(silver_path)
        print("   ✓ Cleared")
    else:
        print("   Keeping existing silver layer")

# Create Spark session
print("\n3. Initializing Spark...")
spark = get_spark("SilverLayerBuilder")
spark.conf.set("spark.sql.shuffle.partitions", "10")
spark.conf.set("spark.sql.files.maxPartitionBytes", "134217728")
print("   ✓ Spark ready")

# Load configs
print("\n4. Loading configurations...")
storage_cfg, model_cfg = load_config(repo_root)
print("   ✓ Configs loaded")

# Build with optimized loader
print("\n5. Building Silver Layer (Optimized)")
print("=" * 70)

builder = CompanySilverBuilder(spark, storage_cfg, model_cfg)
builder.loader = ParquetLoaderOptimized()

# Build dimensions
print("\n📦 Dimensions")
print("-" * 70)

print("\n🏢 dim_company")
dim_company = builder.build_dim_company()
dim_company.cache()
print(f"   Rows: {dim_company.count():,}")

print("\n🏛️  dim_exchange")
dim_exchange = builder.build_dim_exchange()
dim_exchange.cache()
print(f"   Rows: {dim_exchange.count():,}")

# Build facts
print("\n\n📊 Facts")
print("-" * 70)

print("\n💰 fact_prices")
fact_prices = builder.build_fact_prices()
fact_prices.cache()
print(f"   Rows: {fact_prices.count():,}")

print("\n🔗 prices_with_company")
prices_with_company = builder.build_prices_with_company(
    fact_prices, dim_company, dim_exchange
)
prices_with_company.cache()
print(f"   Rows: {prices_with_company.count():,}")

# Write optimized
print("\n\n💾 Writing (Optimized)")
print("=" * 70)

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

# Verify
print("\n\n✅ Build Complete!")
print("=" * 70)

if silver_path.exists():
    import subprocess

    print("\nFile structure:")
    result = subprocess.run(
        ["find", str(silver_path / "company"), "-name", "*.parquet"],
        capture_output=True,
        text=True
    )

    files = result.stdout.strip().split('\n') if result.stdout.strip() else []
    print(f"   Total Parquet files: {len(files)}")

    for f in files[:10]:  # Show first 10
        size_result = subprocess.run(["du", "-h", f], capture_output=True, text=True)
        print(f"   {size_result.stdout.strip()}")

    if len(files) > 10:
        print(f"   ... and {len(files) - 10} more")

    total_size = subprocess.run(
        ["du", "-sh", str(silver_path / "company")],
        capture_output=True,
        text=True
    )
    print(f"\n   Total size: {total_size.stdout.split()[0]}")

# Cleanup
dim_company.unpersist()
dim_exchange.unpersist()
fact_prices.unpersist()
prices_with_company.unpersist()
spark.stop()

print("\n🚀 Ready for fast DuckDB queries!")
print("\nNext steps:")
print("  1. Test: python test_duckdb_pipeline.py")
print("  2. Run app: python run_app.py")
print("  3. Enjoy 10-100x faster queries!")
