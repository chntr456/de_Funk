#!/usr/bin/env python3
"""
Build weighted aggregate views for equity model.

This script creates DuckDB views for weighted aggregate measures
(equal-weighted, volume-weighted, market cap-weighted, etc.).

Usage:
    python scripts/build_weighted_views.py
    python -m scripts.build_weighted_views
"""

import sys
from pathlib import Path

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
from models.builders import WeightedAggregateBuilder
import yaml


def build_weighted_views():
    """Build weighted aggregate views for equity model."""
    print("=" * 70)
    print("Building Weighted Aggregate Views for Equity Model")
    print("=" * 70)

    # Load equity model config
    model_config_path = Path("configs/models/equity.yaml")
    print(f"\n1. Loading equity model config from {model_config_path}...")

    with open(model_config_path, 'r') as f:
        model_cfg = yaml.safe_load(f)

    print(f"   ✓ Loaded config for model: {model_cfg.get('model')}")

    # Get DuckDB connection
    print("\n2. Connecting to DuckDB...")
    ctx = RepoContext.from_repo_root(connection_type="duckdb")
    conn = ctx.connection.conn
    print("   ✓ Connected to analytics.db")

    # Get storage path
    storage_root = model_cfg.get('storage', {}).get('root', 'storage/silver/equity')
    storage_path = Path(storage_root)
    print(f"\n3. Using storage path: {storage_path}")

    # Build weighted aggregates
    print("\n4. Building weighted aggregate views...")
    print("-" * 70)

    try:
        builder = WeightedAggregateBuilder(
            connection=conn,
            model_config=model_cfg,
            storage_path=storage_path
        )

        # Get list of weighted measures
        weighted_measures = builder._get_weighted_aggregate_measures()
        print(f"   Found {len(weighted_measures)} weighted measures to build:")
        for measure_id in weighted_measures:
            print(f"     - {measure_id}")

        print("\n   Creating views...")
        builder.build_all_weighted_aggregates(materialize=False)

        print("\n" + "=" * 70)
        print("✓ SUCCESS: All weighted aggregate views created")
        print("=" * 70)

        # Verify views exist
        print("\n5. Verifying views...")
        for measure_id in weighted_measures:
            try:
                result = conn.execute(f"SELECT COUNT(*) as cnt FROM {measure_id}").fetchone()
                count = result[0]
                print(f"   ✓ {measure_id}: {count:,} rows")
            except Exception as e:
                print(f"   ✗ {measure_id}: Error - {str(e)[:60]}")

        print("\n" + "=" * 70)
        print("Next steps:")
        print("  - Run: python test_weighted_fix.py")
        print("  - Start the app: python run_app.py")
        print("  - View weighted indices in aggregate_stock_analysis notebook")
        print("=" * 70)

        return True

    except Exception as e:
        print("\n" + "=" * 70)
        print(f"✗ ERROR: Failed to build weighted aggregate views")
        print("=" * 70)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    try:
        success = build_weighted_views()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
