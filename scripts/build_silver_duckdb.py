"""
Build Silver Layer using DuckDB (no Spark required).

This script builds the Silver layer from Bronze data using DuckDB,
which is much faster to start up and doesn't require PySpark.

Usage:
    python -m scripts.build_silver_duckdb --model stocks
"""
from __future__ import annotations

import sys
from pathlib import Path
import argparse
import json

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.connection import ConnectionFactory
from config.model_loader import ModelConfigLoader


def main():
    parser = argparse.ArgumentParser(description="Build Silver layer using DuckDB")
    parser.add_argument(
        '--model',
        type=str,
        default='stocks',
        help='Model name to build (default: stocks)'
    )
    args = parser.parse_args()

    print(f"\n{'=' * 70}")
    print(f"Building {args.model.upper()} Model Silver Layer (DuckDB)")
    print(f"{'=' * 70}")

    # Initialize paths
    repo_root_path = Path(repo_root)
    config_root = repo_root_path / "configs" / "models"

    # Load storage config
    storage_cfg_path = repo_root_path / "configs" / "storage.json"
    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    # Create DuckDB connection
    print("\nInitializing DuckDB connection...")
    connection = ConnectionFactory.create(
        "duckdb",
        db_path=":memory:",  # In-memory for building
        auto_init_views=False  # Don't try to init views yet
    )
    print("  ✓ DuckDB connection ready")

    # Load model configuration
    print(f"\nLoading {args.model} model configuration...")
    loader = ModelConfigLoader(config_root)
    model_cfg = loader.load_model_config(args.model)
    print(f"  ✓ Configuration loaded")

    # Import and instantiate the model
    print(f"\nInstantiating {args.model} model...")

    if args.model == 'stocks':
        from models.implemented.stocks.model import StocksModel
        model = StocksModel(
            connection=connection,
            storage_cfg=storage_cfg,
            model_cfg=model_cfg,
            params={},
            repo_root=repo_root
        )
    elif args.model == 'company':
        from models.implemented.company.model import CompanyModel
        model = CompanyModel(
            connection=connection,
            storage_cfg=storage_cfg,
            model_cfg=model_cfg,
            params={},
            repo_root=repo_root
        )
    else:
        raise ValueError(f"Unknown model: {args.model}")

    print(f"  ✓ Model instantiated")

    # Build the model
    print(f"\nBuilding {args.model} model graph...")
    dims, facts = model.build()

    # Report results
    print(f"\n✓ Model built:")
    print(f"  Dimensions:")
    for name, df in dims.items():
        try:
            # DuckDB relation - get count
            if hasattr(df, 'df'):
                count = len(df.df())
            elif hasattr(df, '__len__'):
                count = len(df)
            else:
                count = "unknown"
            print(f"    - {name}: {count} rows")
        except Exception as e:
            print(f"    - {name}: (error getting count: {e})")

    print(f"  Facts:")
    for name, df in facts.items():
        try:
            if hasattr(df, 'df'):
                count = len(df.df())
            elif hasattr(df, '__len__'):
                count = len(df)
            else:
                count = "unknown"
            print(f"    - {name}: {count} rows")
        except Exception as e:
            print(f"    - {name}: (error getting count: {e})")

    # Write to Silver layer
    print(f"\nWriting to Silver layer...")
    try:
        stats = model.write_tables(use_optimized_writer=True)
        print(f"  ✓ Tables written successfully")
        if stats:
            for name, stat in stats.items():
                print(f"    - {name}: {stat.get('rows', 'N/A')} rows")
    except Exception as e:
        print(f"  ⚠ Error writing tables: {e}")
        # Try alternative write method
        print("  Attempting fallback write...")
        try:
            # Write as parquet directly using pandas
            import pandas as pd
            silver_root = repo_root_path / "storage" / "silver" / args.model

            for name, df in {**dims, **facts}.items():
                table_path = silver_root / name
                table_path.mkdir(parents=True, exist_ok=True)

                # Convert to pandas
                if hasattr(df, 'df'):
                    pdf = df.df()
                elif isinstance(df, pd.DataFrame):
                    pdf = df
                else:
                    print(f"    ⚠ Skipping {name} - unknown type: {type(df)}")
                    continue

                # Write as parquet
                output_file = table_path / "data.parquet"
                pdf.to_parquet(output_file, index=False)
                print(f"    ✓ {name}: {len(pdf)} rows → {output_file}")

            print(f"  ✓ Fallback write completed")
        except Exception as e2:
            print(f"  ✗ Fallback write also failed: {e2}")

    print(f"\n{'=' * 70}")
    print(f"✓ Silver layer build complete!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
