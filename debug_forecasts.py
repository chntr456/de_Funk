#!/usr/bin/env python3
"""
Debug forecast data paths and verify everything is set up correctly.
"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

def check_forecast_setup():
    """Check forecast configuration and data existence."""

    print("=" * 70)
    print("FORECAST DATA DEBUGGING")
    print("=" * 70)

    # 1. Check storage configuration
    print("\n1. STORAGE CONFIGURATION")
    print("-" * 70)

    storage_cfg_path = Path("configs/storage.json")
    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    forecast_root = storage_cfg['roots'].get('forecast_silver')
    print(f"Config forecast_silver: {forecast_root}")

    abs_forecast_root = Path(forecast_root).resolve()
    print(f"Absolute path: {abs_forecast_root}")
    print(f"Path exists: {abs_forecast_root.exists()}")

    # 2. Check expected UI paths
    print("\n2. UI EXPECTED PATHS")
    print("-" * 70)

    ui_price_path = Path(forecast_root) / 'facts' / 'forecast_price'
    ui_volume_path = Path(forecast_root) / 'facts' / 'forecast_volume'
    ui_metrics_path = Path(forecast_root) / 'facts' / 'forecast_metrics'

    print(f"Price forecasts: {ui_price_path}")
    print(f"  Exists: {ui_price_path.exists()}")

    print(f"Volume forecasts: {ui_volume_path}")
    print(f"  Exists: {ui_volume_path.exists()}")

    print(f"Metrics: {ui_metrics_path}")
    print(f"  Exists: {ui_metrics_path.exists()}")

    # 3. Check for actual parquet files
    print("\n3. ACTUAL PARQUET FILES")
    print("-" * 70)

    if ui_price_path.exists():
        price_files = list(ui_price_path.rglob('*.parquet'))
        print(f"Found {len(price_files)} price forecast files:")
        for f in price_files[:5]:
            print(f"  - {f}")
        if len(price_files) > 5:
            print(f"  ... and {len(price_files) - 5} more")
    else:
        print("❌ No price forecast directory found")

    if ui_volume_path.exists():
        volume_files = list(ui_volume_path.rglob('*.parquet'))
        print(f"\nFound {len(volume_files)} volume forecast files:")
        for f in volume_files[:5]:
            print(f"  - {f}")
        if len(volume_files) > 5:
            print(f"  ... and {len(volume_files) - 5} more")
    else:
        print("❌ No volume forecast directory found")

    # 4. Check for any forecast-related files anywhere
    print("\n4. SEARCH FOR ANY FORECAST FILES")
    print("-" * 70)

    storage_root = Path("storage")
    if storage_root.exists():
        all_forecast_files = list(storage_root.rglob('*forecast*.parquet'))
        if all_forecast_files:
            print(f"Found {len(all_forecast_files)} forecast-related parquet files:")
            for f in all_forecast_files[:10]:
                print(f"  - {f}")
            if len(all_forecast_files) > 10:
                print(f"  ... and {len(all_forecast_files) - 10} more")
        else:
            print("❌ No forecast parquet files found anywhere in storage/")

    # 5. Test loading with DuckDB (like UI does)
    print("\n5. TEST LOADING WITH DUCKDB (UI METHOD)")
    print("-" * 70)

    try:
        import duckdb

        test_ticker = "AAPL"
        forecast_path = f"storage/silver/forecast/facts/forecast_price"

        con = duckdb.connect(database=':memory:')
        query = f"""
        SELECT COUNT(*) as count, ticker
        FROM read_parquet('{forecast_path}/**/*.parquet')
        WHERE UPPER(ticker) = UPPER('{test_ticker}')
        GROUP BY ticker
        """

        result = con.execute(query).fetchdf()
        con.close()

        if not result.empty:
            print(f"✓ Successfully loaded {result['count'].iloc[0]} forecast records for {test_ticker}")
        else:
            print(f"❌ Query succeeded but returned no data for {test_ticker}")

    except Exception as e:
        print(f"❌ Failed to load with DuckDB: {e}")

    # 6. Recommendations
    print("\n6. RECOMMENDATIONS")
    print("-" * 70)

    if not ui_price_path.exists():
        print("❌ Forecast directories don't exist")
        print("   → Run: python scripts/run_forecasts.py --tickers AAPL,AA")
        print("   → Or: python run_full_pipeline.py --top-n 10")
    elif not any(ui_price_path.rglob('*.parquet')):
        print("❌ Directories exist but no parquet files")
        print("   → Forecasts are not being saved")
        print("   → Check pipeline output for errors")
    else:
        print("✓ Forecast files exist!")
        print("   → Check UI is looking at correct path")
        print("   → Try refreshing UI browser cache")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    check_forecast_setup()
