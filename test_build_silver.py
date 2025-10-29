#!/usr/bin/env python3
"""
Test script for building Silver layer.

This script:
1. Loads Bronze data
2. Builds Silver layer tables (dims, facts, paths)
3. Writes to storage/silver/
4. Shows sample data from each table

Usage:
    python test_build_silver.py
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("Silver Layer Build Test")
print("=" * 60)

try:
    # Import dependencies
    print("\n1. Loading dependencies...")
    from src.orchestration.context import RepoContext
    from src.model.silver.company_silver_builder import CompanySilverBuilder, load_config
    print("   ✓ Dependencies loaded")

    # Initialize context
    print("\n2. Initializing Spark context...")
    ctx = RepoContext.from_repo_root()
    print(f"   ✓ Repo root: {ctx.repo}")
    print(f"   ✓ Spark session: {ctx.spark.version}")

    # Load configs
    print("\n3. Loading configurations...")
    storage_cfg, model_cfg = load_config(ctx.repo)
    print(f"   ✓ Storage config loaded")
    print(f"   ✓ Model config loaded (model: {model_cfg['model']})")

    # Check Bronze data exists
    print("\n4. Checking Bronze data...")
    bronze_root = Path(storage_cfg["roots"]["bronze"])
    if not bronze_root.exists():
        print(f"   ✗ ERROR: Bronze layer not found at {bronze_root}")
        sys.exit(1)

    # Count Bronze files
    bronze_files = list(bronze_root.rglob("*.parquet"))
    print(f"   ✓ Bronze data found: {len(bronze_files)} parquet files")

    # Show Bronze tables
    print("\n   Bronze tables:")
    for table_name, table_cfg in storage_cfg["tables"].items():
        if table_cfg.get("root") == "bronze":
            table_path = bronze_root / table_cfg["rel"]
            if table_path.exists():
                print(f"     • {table_name}")

    # Build Silver layer
    print("\n5. Building Silver layer...")
    print("   This may take a minute...")
    builder = CompanySilverBuilder(ctx.spark, storage_cfg, model_cfg)

    snapshot_date = "2024-01-05"
    print(f"\n   Building with snapshot_date={snapshot_date}")
    print("   " + "-" * 56)

    builder.build_and_write(snapshot_date=snapshot_date)

    print("   " + "-" * 56)
    print("   ✓ Silver layer build complete!")

    # Verify Silver layer
    print("\n6. Verifying Silver layer...")
    silver_root = Path(storage_cfg["roots"]["silver"])

    if not silver_root.exists():
        print(f"   ✗ ERROR: Silver layer not created at {silver_root}")
        sys.exit(1)

    silver_files = list(silver_root.rglob("*.parquet"))
    print(f"   ✓ Silver data created: {len(silver_files)} parquet files")

    # Show Silver tables
    print("\n   Silver tables created:")
    for table_name, table_cfg in storage_cfg["tables"].items():
        if table_cfg.get("root") == "silver":
            table_path = silver_root / table_cfg["rel"]
            if table_path.exists():
                # Try to read and count rows
                try:
                    df = ctx.spark.read.parquet(str(table_path))
                    count = df.count()
                    print(f"     • {table_name}: {count:,} rows")
                except Exception as e:
                    print(f"     • {table_name}: exists (count failed)")

    # Show sample data
    print("\n7. Sample data from Silver layer:")
    print("   " + "-" * 56)

    # Sample from dim_company
    print("\n   dim_company (first 5 rows):")
    dim_company_path = silver_root / storage_cfg["tables"]["dim_company"]["rel"]
    if dim_company_path.exists():
        df = ctx.spark.read.parquet(str(dim_company_path))
        df.show(5, truncate=False)

    # Sample from fact_prices
    print("\n   fact_prices (first 5 rows):")
    fact_prices_path = silver_root / storage_cfg["tables"]["fact_prices"]["rel"]
    if fact_prices_path.exists():
        df = ctx.spark.read.parquet(str(fact_prices_path))
        df.show(5, truncate=False)

    # Sample from prices_with_company
    print("\n   prices_with_company (first 5 rows):")
    prices_with_company_path = silver_root / storage_cfg["tables"]["prices_with_company"]["rel"]
    if prices_with_company_path.exists():
        df = ctx.spark.read.parquet(str(prices_with_company_path))
        df.show(5, truncate=False)

    # Stop Spark
    print("\n8. Cleaning up...")
    ctx.spark.stop()
    print("   ✓ Spark session stopped")

    # Success summary
    print("\n" + "=" * 60)
    print("✓ SUCCESS: Silver layer built successfully!")
    print("=" * 60)
    print(f"\nSilver layer location: {silver_root}")
    print("\nYou can now:")
    print("  1. Run the UI: streamlit run src/ui/notebook_app_professional.py")
    print("  2. Update UI to use new NotebookService")
    print("  3. Query Silver layer directly for analysis")
    print()

except ImportError as e:
    print(f"\n✗ ERROR: Missing dependency: {e}")
    print("\nMake sure you have installed all requirements:")
    print("  pip install pyspark")
    sys.exit(1)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
