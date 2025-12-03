#!/usr/bin/env python
"""
Build Company Model - Build silver layer from bronze.

Usage:
    python -m scripts.build_company_model
"""
from __future__ import annotations

import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config.logging import setup_logging, get_logger

logger = get_logger(__name__)


def main():
    """Build the company model."""
    setup_logging()

    print("=" * 70)
    print("BUILDING COMPANY MODEL")
    print("=" * 70)
    print()

    # Initialize Spark (required for model builds)
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder \
            .appName("BuildCompanyModel") \
            .config("spark.driver.memory", "8g") \
            .config("spark.sql.parquet.compression.codec", "snappy") \
            .getOrCreate()
        print("✓ Spark session created")
    except Exception as e:
        print(f"✗ Failed to create Spark session: {e}")
        return 1

    # Load model
    try:
        from models.implemented.company.model import CompanyModel

        print("\nLoading company model configuration...")
        model = CompanyModel(spark=spark)
        print(f"✓ Model loaded: {model.name}")

    except Exception as e:
        print(f"✗ Failed to load model: {e}")
        spark.stop()
        return 1

    # Build model
    try:
        print("\nBuilding silver layer from bronze...")
        print("-" * 70)

        dims, facts = model.build()

        print("\n✓ Build complete!")
        print(f"\nDimensions built: {len(dims)}")
        for name, df in dims.items():
            count = df.count() if hasattr(df, 'count') else len(df)
            print(f"  - {name}: {count:,} rows")

        print(f"\nFacts built: {len(facts)}")
        for name, df in facts.items():
            count = df.count() if hasattr(df, 'count') else len(df)
            print(f"  - {name}: {count:,} rows")

    except Exception as e:
        print(f"✗ Build failed: {e}")
        import traceback
        traceback.print_exc()
        spark.stop()
        return 1

    # Write to silver layer
    try:
        print("\nWriting to silver layer...")
        print("-" * 70)

        model.write()
        print("✓ Written to silver layer")

    except Exception as e:
        print(f"✗ Write failed: {e}")
        import traceback
        traceback.print_exc()
        spark.stop()
        return 1

    print("\n" + "=" * 70)
    print("✓ COMPANY MODEL BUILD COMPLETE")
    print("=" * 70)

    spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
