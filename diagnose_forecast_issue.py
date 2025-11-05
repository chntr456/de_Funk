"""
Diagnostic script to understand forecast loading issue.

This script checks:
1. What forecasts exist in storage
2. What the UI expects to load
3. Differences in file structure/schema
4. Whether files are accessible
"""

import sys
from pathlib import Path
import json

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

def check_forecast_storage():
    """Check what forecast files exist in storage."""
    print("=" * 80)
    print("FORECAST STORAGE DIAGNOSTIC")
    print("=" * 80)
    print()

    # Load storage config
    with open("configs/storage.json") as f:
        storage_cfg = json.load(f)

    forecast_root = Path(storage_cfg['roots'].get('forecast_silver', 'storage/silver/forecast'))

    print(f"1. Forecast root: {forecast_root}")
    print(f"   Exists: {forecast_root.exists()}")
    print()

    if not forecast_root.exists():
        print("❌ Forecast directory doesn't exist!")
        print("   Run: python scripts/run_forecasts.py --tickers AAPL")
        return

    # Check directory structure
    print("2. Directory structure:")
    for path in sorted(forecast_root.rglob("*")):
        rel_path = path.relative_to(forecast_root)
        if path.is_dir():
            print(f"   📁 {rel_path}/")
        elif path.suffix == '.parquet':
            size_kb = path.stat().st_size / 1024
            print(f"   📄 {rel_path} ({size_kb:.1f} KB)")
    print()

    # Check forecast_price specifically
    forecast_price_path = forecast_root / "facts" / "forecast_price"
    print(f"3. Forecast price path: {forecast_price_path}")
    print(f"   Exists: {forecast_price_path.exists()}")
    print()

    if forecast_price_path.exists():
        parquet_files = list(forecast_price_path.rglob("*.parquet"))
        print(f"   Found {len(parquet_files)} parquet files")

        if parquet_files:
            # Load and inspect one file
            try:
                import pandas as pd
                sample_file = parquet_files[0]
                print(f"\n4. Sample file: {sample_file.relative_to(forecast_root)}")

                df = pd.read_parquet(sample_file)
                print(f"   Rows: {len(df)}")
                print(f"   Columns: {list(df.columns)}")
                print(f"\n   Sample data:")
                print(df.head(3).to_string(index=False))
                print()

                print(f"   Unique tickers: {df['ticker'].unique().tolist() if 'ticker' in df.columns else 'N/A'}")
                print(f"   Unique models: {df['model_name'].unique().tolist() if 'model_name' in df.columns else 'N/A'}")
            except Exception as e:
                print(f"   ❌ Error reading file: {e}")
    else:
        print("   ❌ forecast_price directory not found!")

    print()

    # Check forecast_volume
    forecast_volume_path = forecast_root / "facts" / "forecast_volume"
    print(f"5. Forecast volume path: {forecast_volume_path}")
    print(f"   Exists: {forecast_volume_path.exists()}")

    if forecast_volume_path.exists():
        vol_files = list(forecast_volume_path.rglob("*.parquet"))
        print(f"   Found {len(vol_files)} parquet files")
    print()

    # Check metrics
    metrics_path = forecast_root / "facts" / "forecast_metrics"
    print(f"6. Forecast metrics path: {metrics_path}")
    print(f"   Exists: {metrics_path.exists()}")

    if metrics_path.exists():
        metric_files = list(metrics_path.rglob("*.parquet"))
        print(f"   Found {len(metric_files)} parquet files")
    print()

    # Test UI loading
    print("7. Testing UI load method:")
    try:
        import duckdb
        forecast_path = f"{forecast_price_path}/**/*.parquet"
        con = duckdb.connect(database=':memory:')

        # Try to load all forecasts
        query = f"""
        SELECT ticker, model_name, COUNT(*) as num_forecasts
        FROM read_parquet('{forecast_path}')
        GROUP BY ticker, model_name
        ORDER BY ticker, model_name
        """
        df = con.execute(query).fetchdf()
        con.close()

        if len(df) > 0:
            print("   ✅ DuckDB can load forecasts!")
            print(f"\n   Available forecasts:")
            print(df.to_string(index=False))
        else:
            print("   ❌ No forecasts found by DuckDB")

    except Exception as e:
        print(f"   ❌ DuckDB load failed: {e}")

    print()
    print("=" * 80)


def main():
    try:
        check_forecast_storage()
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
