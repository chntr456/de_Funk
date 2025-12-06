#!/usr/bin/env python3
"""
Build Silver Layer Script.

Uses BaseModel.write_tables() to materialize the Silver layer from Bronze data.

Usage:
    python -m scripts.build_silver_layer [--model MODEL_NAME]

Examples:
    python -m scripts.build_silver_layer --model company
    python -m scripts.build_silver_layer --model macro
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


def main():
    parser = argparse.ArgumentParser(description="Build Silver layer from Bronze using BaseModel")
    parser.add_argument(
        '--model',
        type=str,
        default='company',
        help='Model name to build (default: company)'
    )
    args = parser.parse_args()

    # Initialize - use repo_root from setup_repo_imports() (already set at module level)
    spark = get_spark("SilverLayerBuilder")

    # Load storage config
    storage_cfg_path = repo_root / "configs" / "storage.json"
    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    print(f"\n{'=' * 70}")
    print(f"Building {args.model.upper()} Model Silver Layer")
    print(f"{'=' * 70}")

    # Create UniversalSession
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root
    )

    # Load and build model
    model = session.load_model(args.model)
    print(f"Building {args.model} model graph...")
    model.ensure_built()

    # List tables
    tables = model.list_tables()
    print(f"✓ Model built:")
    print(f"  - Dimensions: {tables['dimensions']}")
    print(f"  - Facts: {tables['facts']}")

    # Write to Silver layer using BaseModel.write_tables()
    stats = model.write_tables(use_optimized_writer=True)

    print(f"\n{'=' * 70}")
    print(f"✓ Silver layer build complete!")
    print(f"{'=' * 70}")

    spark.stop()


if __name__ == "__main__":
    main()
