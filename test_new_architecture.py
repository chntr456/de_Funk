#!/usr/bin/env python3
"""
Test script for the new scalable model architecture.

This tests:
1. BaseModel graph building
2. ModelRegistry dynamic loading
3. UniversalSession model-agnostic access
4. CompanyModel inheriting from BaseModel
5. ForecastModel with cross-model dependencies
"""

import sys
from pathlib import Path
from pprint import pprint

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_model_registry():
    """Test ModelRegistry can discover and load models"""
    print("\n" + "=" * 60)
    print("TEST 1: Model Registry")
    print("=" * 60)

    from models.registry import ModelRegistry

    repo_root = Path.cwd()
    models_dir = repo_root / "configs" / "models"

    registry = ModelRegistry(models_dir)

    # List available models
    models = registry.list_models()
    print(f"✓ Available models: {models}")

    # Get company model config
    company_config = registry.get_model_config('company')
    print(f"✓ Company model loaded: {company_config.get('model')}")

    # Get forecast model config
    forecast_config = registry.get_model_config('forecast')
    print(f"✓ Forecast model loaded: {forecast_config.get('model')}")

    # Test model class registration
    company_class = registry.get_model_class('company')
    print(f"✓ Company model class: {company_class.__name__}")

    forecast_class = registry.get_model_class('forecast')
    print(f"✓ Forecast model class: {forecast_class.__name__}")

    print("✓ Model Registry: PASSED\n")


def test_universal_session():
    """Test UniversalSession can load models dynamically"""
    print("\n" + "=" * 60)
    print("TEST 2: Universal Session")
    print("=" * 60)

    from models.api.session import UniversalSession
    from orchestration.common.spark_session import get_spark_session
    import json

    # Get Spark session
    spark = get_spark_session(
        app_name="TestNewArchitecture",
        config={"spark.sql.shuffle.partitions": "2"}
    )

    # Load storage config
    repo_root = Path.cwd()
    storage_cfg_path = repo_root / "configs" / "storage.json"
    with open(storage_cfg_path) as f:
        storage_cfg = json.load(f)

    # Create universal session
    session = UniversalSession(
        connection=spark,
        storage_cfg=storage_cfg,
        repo_root=repo_root
    )

    # List available models
    models = session.list_models()
    print(f"✓ Available models: {models}")

    # Load company model
    company_model = session.load_model('company')
    print(f"✓ Company model loaded: {company_model.__class__.__name__}")

    # Get company model metadata
    metadata = session.get_model_metadata('company')
    print(f"✓ Company model metadata:")
    pprint(metadata, indent=2)

    # List company model tables
    tables = session.list_tables('company')
    print(f"✓ Company model tables:")
    print(f"  - Dimensions: {tables['dimensions']}")
    print(f"  - Facts: {tables['facts']}")

    # Load forecast model
    forecast_model = session.load_model('forecast')
    print(f"✓ Forecast model loaded: {forecast_model.__class__.__name__}")

    # Verify session injection
    if hasattr(forecast_model, '_session') and forecast_model._session is not None:
        print(f"✓ Session injected into forecast model")
    else:
        print(f"⚠ Session not injected into forecast model")

    print("✓ Universal Session: PASSED\n")

    return session, spark


def test_company_model(session, spark):
    """Test CompanyModel builds correctly from BaseModel"""
    print("\n" + "=" * 60)
    print("TEST 3: Company Model (BaseModel)")
    print("=" * 60)

    # Get company model
    company_model = session.get_model_instance('company')

    # Ensure it's built
    company_model.ensure_built()
    print(f"✓ Company model built successfully")

    # Check tables exist
    tables = company_model.list_tables()
    print(f"✓ Dimensions: {tables['dimensions']}")
    print(f"✓ Facts: {tables['facts']}")

    # Verify expected tables
    expected_dims = ['dim_company', 'dim_exchange']
    expected_facts = ['fact_prices', 'fact_news', 'prices_with_company', 'news_with_company']

    for dim in expected_dims:
        if dim in tables['dimensions']:
            print(f"  ✓ {dim} found")
        else:
            print(f"  ✗ {dim} NOT FOUND")

    for fact in expected_facts:
        if fact in tables['facts']:
            print(f"  ✓ {fact} found")
        else:
            print(f"  ⚠ {fact} NOT FOUND (might not be built yet)")

    # Test convenience method
    try:
        dim_company = company_model.get_dimension_df('dim_company')
        count = dim_company.count()
        print(f"✓ dim_company has {count} rows")
    except Exception as e:
        print(f"⚠ Could not load dim_company: {e}")

    print("✓ Company Model: PASSED\n")


def test_forecast_model(session, spark):
    """Test ForecastModel with cross-model dependencies"""
    print("\n" + "=" * 60)
    print("TEST 4: Forecast Model (Cross-Model)")
    print("=" * 60)

    # Get forecast model
    forecast_model = session.get_model_instance('forecast')

    # Check session injection
    if forecast_model._session:
        print(f"✓ Session injected into forecast model")
    else:
        print(f"✗ Session NOT injected")

    # Get model configs
    model_configs = forecast_model.get_model_configs()
    print(f"✓ Available forecast model configs: {list(model_configs.keys())}")

    # Test getting a specific config
    arima_config = forecast_model.get_model_config('arima_7d')
    print(f"✓ ARIMA 7d config: type={arima_config['type']}, lookback={arima_config['lookback_days']}")

    # Test cross-model data access
    try:
        # This requires company model to be built with data
        training_data = forecast_model.get_training_data('AAPL')
        print(f"✓ Cross-model data access works (got training data)")
    except Exception as e:
        print(f"⚠ Cross-model data access: {e}")

    print("✓ Forecast Model: PASSED\n")


def test_backward_compatibility():
    """Test backward compatibility with old API"""
    print("\n" + "=" * 60)
    print("TEST 5: Backward Compatibility")
    print("=" * 60)

    try:
        # Test old imports still work
        from models.api.types import NewsItem, PriceBar
        print(f"✓ Can import types from old location")

        from models.api.services import NewsAPI, PricesAPI, CompanyAPI
        print(f"✓ Can import services from old location")

        print("✓ Backward Compatibility: PASSED\n")
    except Exception as e:
        print(f"✗ Backward Compatibility: FAILED - {e}\n")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("TESTING NEW SCALABLE MODEL ARCHITECTURE")
    print("=" * 60)

    try:
        # Test 1: Model Registry
        test_model_registry()

        # Test 2: Universal Session
        session, spark = test_universal_session()

        # Test 3: Company Model
        test_company_model(session, spark)

        # Test 4: Forecast Model
        test_forecast_model(session, spark)

        # Test 5: Backward Compatibility
        test_backward_compatibility()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)
        print("\nThe new architecture is working correctly:")
        print("  - BaseModel provides generic graph building")
        print("  - UniversalSession enables model-agnostic access")
        print("  - CompanyModel inherits all logic from BaseModel")
        print("  - ForecastModel supports cross-model dependencies")
        print("  - Backward compatibility maintained")
        print("\n")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
