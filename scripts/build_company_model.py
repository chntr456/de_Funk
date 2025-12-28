#!/usr/bin/env python
"""
Build Company Model - Build silver layer from bronze.

Usage:
    python -m scripts.build_company_model
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from config import ConfigLoader
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
        from orchestration.common.spark_session import get_spark
        spark = get_spark(
            app_name="BuildCompanyModel",
            config={
                "spark.driver.memory": "8g",
                "spark.sql.parquet.compression.codec": "snappy",
            }
        )
        print("✓ Spark session created (with Delta Lake support)")
    except Exception as e:
        print(f"✗ Failed to create Spark session: {e}")
        return 1

    # Load configuration
    try:
        # Use ConfigLoader for properly resolved storage paths
        config = ConfigLoader().load()
        storage_cfg = config.storage
        print("✓ Storage config loaded")

        # Load model config using ModelConfigLoader (handles modular YAMLs)
        from config.model_loader import ModelConfigLoader
        models_dir = repo_root / "configs" / "models"
        loader = ModelConfigLoader(models_dir)
        model_cfg = loader.load_model_config("company")
        print("✓ Model config loaded")

    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        spark.stop()
        return 1

    # Load model with correct initialization
    try:
        from models.domain.company.model import CompanyModel

        print("\nInitializing company model...")
        model = CompanyModel(
            connection=spark,
            storage_cfg=storage_cfg,
            model_cfg=model_cfg,
            params={},
            repo_root=repo_root
        )
        print(f"✓ Model initialized: {model.model_name}")

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

        # Paths are already absolute from ConfigLoader
        output_path = storage_cfg["roots"].get("company_silver")
        if not output_path:
            output_path = storage_cfg["roots"]["silver"] + "/company"

        model.write_tables(output_root=output_path, quiet=True)
        print(f"✓ Written to silver layer: {output_path}")

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
