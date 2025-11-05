#!/usr/bin/env python3
"""
Quick test script to verify forecast generation and persistence.
Tests the full pipeline for a single ticker.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from orchestration.common.spark_session import get_spark
from models.api.session import UniversalSession
import json

def test_forecast_for_ticker(ticker: str = "AAPL"):
    """Test forecast generation for a single ticker."""

    print(f"Testing forecast generation for {ticker}...")
    print("=" * 70)

    # Initialize Spark
    spark = get_spark("ForecastTest")

    # Load configurations
    repo_root = Path(__file__).parent
    storage_cfg_path = repo_root / "configs" / "storage.json"

    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    # Create session
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root,
        models=['company', 'forecast']
    )

    # Get forecast model
    forecast_model = session.get_model_instance('forecast')
    forecast_model.set_session(session)

    print(f"✓ Loaded forecast model")

    # Run forecasts for this ticker
    print(f"\nRunning forecasts for {ticker}...")
    results = forecast_model.run_forecast_for_ticker(ticker)

    # Print results
    print("\nResults:")
    print(f"  Models trained: {results['models_trained']}")
    print(f"  Forecasts generated: {results['forecasts_generated']}")
    print(f"  Errors: {len(results['errors'])}")

    if results['errors']:
        print("\nErrors:")
        for error in results['errors'][:5]:
            print(f"  - {error}")

    # Check if files were created
    forecast_root = Path(storage_cfg['roots']['forecast_silver'])
    price_path = forecast_root / 'facts' / 'forecast_price'

    if price_path.exists():
        parquet_files = list(price_path.rglob('*.parquet'))
        print(f"\n✓ Created {len(parquet_files)} price forecast files")
        if parquet_files:
            print(f"  Example: {parquet_files[0]}")
    else:
        print(f"\n✗ No forecast files found at {price_path}")

    spark.stop()

    print("\n" + "=" * 70)
    print("Test complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test forecast generation")
    parser.add_argument('--ticker', type=str, default='AAPL', help='Ticker to test')
    args = parser.parse_args()

    test_forecast_for_ticker(args.ticker)
