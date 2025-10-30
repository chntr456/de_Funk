#!/usr/bin/env python3
"""
Build Silver Layer Script.

Runs the CompanySilverBuilder to materialize the Silver layer from Bronze data.

Usage:
    python scripts/build_silver_layer.py [--snapshot-date YYYY-MM-DD]
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.common.spark_session import get_spark
from src.model.silver.company_silver_builder import CompanySilverBuilder, load_config


def main():
    parser = argparse.ArgumentParser(description="Build Silver layer from Bronze")
    parser.add_argument(
        "--snapshot-date",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Snapshot date (YYYY-MM-DD), defaults to today"
    )
    args = parser.parse_args()

    # Initialize
    repo_root = Path(__file__).parent.parent
    spark = get_spark("SilverLayerBuilder")

    # Load configs
    storage_cfg, model_cfg = load_config(repo_root)

    # Build Silver layer
    builder = CompanySilverBuilder(spark, storage_cfg, model_cfg)
    builder.build_and_write(snapshot_date=args.snapshot_date)

    spark.stop()


if __name__ == "__main__":
    main()
