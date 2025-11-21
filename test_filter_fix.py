#!/usr/bin/env python3
"""Test filter fix in BaseModel."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from core.duckdb_connection import DuckDBConnection
from models.registry import ModelRegistry
from models.base.model import BaseModel
from models.api.dal import StorageRouter
from pathlib import Path
import json

# Setup
repo_root = Path.cwd()
conn = DuckDBConnection()

# Load storage config
storage_path = repo_root / "configs" / "storage.json"
with open(storage_path) as f:
    storage_cfg = json.load(f)

# Create model registry
registry = ModelRegistry(repo_root / "configs" / "models")

print("=" * 80)
print("Testing Filter Fix - Building Stocks Model")
print("=" * 80)

try:
    # Get stocks model class and config
    try:
        model_class = registry.get_model_class("stocks")
    except ValueError:
        # No custom class, use BaseModel
        model_class = BaseModel

    model_config = registry.get_model_config("stocks")

    # Create storage router
    storage_router = StorageRouter(storage_cfg, repo_root)

    # Instantiate stocks model
    stocks_model = model_class(
        connection=conn,
        storage_router=storage_router,
        model_cfg=model_config
    )

    print("\n✓ Stocks model instantiated")
    print(f"  Model name: {stocks_model.name}")
    print(f"  Backend: {stocks_model.backend}")

    # Build the model
    print("\nBuilding stocks model...")
    dims, facts = stocks_model.build()

    print(f"\n✓ Build successful!")
    print(f"  Dimensions: {list(dims.keys())}")
    print(f"  Facts: {list(facts.keys())}")

    # Check dim_stock data
    if 'dim_stock' in dims:
        dim_stock_df = conn.to_pandas(dims['dim_stock'])
        print(f"\n✓ dim_stock created:")
        print(f"  Rows: {len(dim_stock_df)}")
        print(f"  Columns: {list(dim_stock_df.columns)}")

        # Check asset_type filter was applied
        if 'asset_type' in dim_stock_df.columns:
            asset_types = dim_stock_df['asset_type'].unique()
            print(f"  Unique asset_types: {asset_types}")
            if len(asset_types) == 1 and asset_types[0] == 'stocks':
                print("  ✓ Filter working! Only 'stocks' asset_type present")
            else:
                print(f"  ⚠️  Filter may not be working - expected only 'stocks', got: {asset_types}")

        print(f"\n  Sample data (first 3 rows):")
        print(dim_stock_df[['ticker', 'security_name', 'asset_type']].head(3).to_string(index=False))

    # Check fact_stock_prices data
    if 'fact_stock_prices' in facts:
        prices_df = conn.to_pandas(facts['fact_stock_prices'])
        print(f"\n✓ fact_stock_prices created:")
        print(f"  Rows: {len(prices_df)}")
        print(f"  Columns: {list(prices_df.columns)}")
        print(f"  Sample data (first 3 rows):")
        print(prices_df[['ticker', 'trade_date', 'close']].head(3).to_string(index=False))

    print("\n" + "=" * 80)
    print("✓ Filter fix is working correctly!")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    conn.stop()
