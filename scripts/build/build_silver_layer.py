#!/usr/bin/env python3
"""
Build Silver Layer Script.

Uses BaseModel.write_tables() to materialize the Silver layer from Bronze data.

Usage:
    python -m scripts.build.build_silver_layer [--model MODEL_NAME]

Examples:
    python -m scripts.build.build_silver_layer              # Build all models
    python -m scripts.build.build_silver_layer --model stocks  # Build specific model
"""

import sys
from pathlib import Path

import argparse
import json
import yaml
from utils.repo import setup_repo_imports

repo_root = setup_repo_imports()

from orchestration.common.spark_session import get_spark
from models.api.session import UniversalSession

# Models in dependency order (core first, then models that depend on it)
# Note: Only include models that have complete implementations
BUILDABLE_MODELS = [
    "core",      # Calendar dimension - foundation for all models
    "company",   # Corporate entities (standalone)
    "stocks",    # Stock securities (depends on core, company)
    # "options", # Partial implementation - uncomment when ready
    # "etfs",    # Skeleton - uncomment when ready
    # "futures", # Skeleton - uncomment when ready
]


def ensure_calendar_seed(spark) -> bool:
    """
    Ensure calendar_seed exists in Bronze layer.

    The core model reads from bronze.calendar_seed, which is generated data
    (not ingested from an API). This function creates it if missing.

    Args:
        spark: SparkSession

    Returns:
        True if calendar seed exists or was created
    """
    calendar_seed_path = repo_root / "storage" / "bronze" / "calendar_seed"

    if calendar_seed_path.exists():
        print("  Calendar seed already exists in Bronze")
        return True

    print("  Calendar seed not found - generating...")

    from models.implemented.core.builders.calendar_builder import CalendarBuilder

    # Generate calendar data (2000-2050)
    builder = CalendarBuilder(
        start_date="2000-01-01",
        end_date="2050-12-31",
        fiscal_year_start_month=1
    )
    calendar_df = builder.build_spark_dataframe(spark)

    # Write to Bronze
    calendar_df.write.format("delta").mode("overwrite").save(str(calendar_seed_path))
    row_count = calendar_df.count()
    print(f"  Generated {row_count:,} calendar rows to Bronze")

    return True


def build_model(session, model_name: str, spark=None) -> dict:
    """
    Build a single model and return stats.

    Args:
        session: UniversalSession instance
        model_name: Name of model to build
        spark: SparkSession (needed for core model calendar seed)

    Returns:
        Dict with build stats or error info
    """
    print(f"\n{'=' * 70}")
    print(f"Building {model_name.upper()} Model Silver Layer")
    print(f"{'=' * 70}")

    try:
        # Core model needs calendar seed in Bronze
        if model_name == "core" and spark is not None:
            ensure_calendar_seed(spark)

        # Load and build model
        model = session.load_model(model_name)
        print(f"Building {model_name} model graph...")
        model.ensure_built()

        # List tables
        tables = model.list_tables()
        print(f"✓ Model built:")
        print(f"  - Dimensions: {tables['dimensions']}")
        print(f"  - Facts: {tables['facts']}")

        # Write to Silver layer using BaseModel.write_tables()
        stats = model.write_tables(use_optimized_writer=True)

        return {
            "status": "success",
            "model": model_name,
            "tables": tables,
            "stats": stats
        }

    except Exception as e:
        print(f"✗ Failed to build {model_name}: {e}")
        return {
            "status": "error",
            "model": model_name,
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Build Silver layer from Bronze using BaseModel")
    parser.add_argument(
        '--model',
        type=str,
        default=None,
        help='Model name to build (default: build ALL models)'
    )
    args = parser.parse_args()

    # Initialize - use repo_root from setup_repo_imports() (already set at module level)
    spark = get_spark("SilverLayerBuilder")

    # Load storage config
    storage_cfg_path = repo_root / "configs" / "storage.json"
    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    # Create UniversalSession
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root
    )

    # Determine which models to build
    if args.model:
        models_to_build = [args.model]
    else:
        models_to_build = BUILDABLE_MODELS
        print(f"\n{'=' * 70}")
        print(f"Building ALL Silver Layer Models")
        print(f"Models: {', '.join(models_to_build)}")
        print(f"{'=' * 70}")

    # Build each model
    results = []
    for model_name in models_to_build:
        result = build_model(session, model_name, spark=spark)
        results.append(result)

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"Silver Layer Build Summary")
    print(f"{'=' * 70}")

    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "error"]

    print(f"\n✓ Successful: {len(successful)}")
    for r in successful:
        tables = r.get("tables", {})
        dim_count = len(tables.get("dimensions", []))
        fact_count = len(tables.get("facts", []))
        print(f"  - {r['model']}: {dim_count} dimensions, {fact_count} facts")

    if failed:
        print(f"\n✗ Failed: {len(failed)}")
        for r in failed:
            print(f"  - {r['model']}: {r['error']}")

    print(f"\n{'=' * 70}")
    print(f"✓ Silver layer build complete!")
    print(f"{'=' * 70}")

    spark.stop()


if __name__ == "__main__":
    main()
