#!/usr/bin/env python3
"""
Test forecast generation using the same method as full pipeline.
This will help identify why full pipeline doesn't save forecasts.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from orchestration.common.spark_session import get_spark
from models.api.session import UniversalSession

def test_pipeline_method():
    """Test forecast generation using full pipeline approach."""

    print("=" * 70)
    print("TEST FORECAST GENERATION (FULL PIPELINE METHOD)")
    print("=" * 70)

    # Load configs
    repo_root = Path(__file__).parent
    storage_cfg_path = repo_root / "configs" / "storage.json"

    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    # Initialize Spark
    spark = get_spark("TestForecastPipeline")

    # Create session (same as full pipeline)
    print("\n1. Creating UniversalSession...")
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root,
        models=['company', 'forecast']
    )
    print("✓ Session created")

    # Get forecast model (same as full pipeline)
    print("\n2. Getting forecast model instance...")
    forecast_model = session.get_model_instance('forecast')
    print(f"✓ Got model: {type(forecast_model)}")
    print(f"   Model config keys: {list(forecast_model.model_cfg.keys())}")
    print(f"   Storage config roots: {list(forecast_model.storage_cfg.get('roots', {}).keys())}")

    # Set session (same as full pipeline)
    print("\n3. Setting session...")
    forecast_model.set_session(session)
    print("✓ Session set")

    # Test with one ticker
    test_ticker = "AAPL"
    print(f"\n4. Running forecasts for {test_ticker}...")
    print("-" * 70)

    try:
        results = forecast_model.run_forecast_for_ticker(test_ticker)

        print(f"\n5. Results:")
        print(f"   Models trained: {results['models_trained']}")
        print(f"   Forecasts generated: {results['forecasts_generated']}")
        print(f"   Errors: {len(results['errors'])}")

        if results['errors']:
            print(f"\n   Errors encountered:")
            for error in results['errors']:
                print(f"     - {error}")

    except Exception as e:
        print(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()

    # Check if files were created
    print("\n6. Checking for output files...")
    print("-" * 70)

    forecast_root = Path(storage_cfg['roots']['forecast_silver'])
    price_path = forecast_root / 'facts' / 'forecast_price'

    if price_path.exists():
        files = list(price_path.rglob('*.parquet'))
        print(f"✓ Found {len(files)} price forecast files")
        for f in files[:3]:
            print(f"   - {f}")
    else:
        print(f"❌ No files found at {price_path}")
        print(f"   Path exists: {price_path.exists()}")
        print(f"   Parent exists: {price_path.parent.exists()}")

    spark.stop()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_pipeline_method()
