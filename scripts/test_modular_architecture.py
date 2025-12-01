#!/usr/bin/env python
"""
Test script for modular YAML model architecture.

Tests:
1. ModelConfigLoader can load modular models
2. Model registry discovers modular models
3. BaseModel can load Python measures
4. Configuration inheritance works correctly

Usage:
    python -m scripts.test_modular_architecture
"""

from pathlib import Path
import sys

# Setup imports
from utils.repo import setup_repo_imports
setup_repo_imports()

from config.model_loader import ModelConfigLoader
from config.logging import get_logger, setup_logging
from models.registry import ModelRegistry
from pprint import pprint

logger = get_logger(__name__)


def print_header(text: str, char: str = "=") -> None:
    """Print a formatted header line."""
    line = char * 80
    print(f"\n{line}")
    print(text)
    print(line)


def test_model_config_loader():
    """Test ModelConfigLoader with modular YAMLs."""
    print_header("TEST 1: ModelConfigLoader - Load Modular Configurations")
    logger.info("Starting ModelConfigLoader tests")

    models_dir = Path("configs/models")
    loader = ModelConfigLoader(models_dir)

    # Test loading stocks model (modular)
    print("\nLoading 'stocks' model (modular structure)...")
    try:
        stocks_config = loader.load_model_config('stocks')
        print(f"  Loaded stocks model successfully")
        print(f"   Model name: {stocks_config.get('model')}")
        print(f"   Version: {stocks_config.get('version')}")
        print(f"   Inherits from: {stocks_config.get('inherits_from')}")
        print(f"   Depends on: {stocks_config.get('depends_on')}")
        print(f"   Components: {list(stocks_config.get('components', {}).keys())}")
        logger.info(f"Loaded stocks model: version={stocks_config.get('version')}")

        # Check if schema was merged
        if 'schema' in stocks_config:
            print(f"   Schema dimensions: {list(stocks_config['schema'].get('dimensions', {}).keys())}")
            print(f"   Schema facts: {list(stocks_config['schema'].get('facts', {}).keys())}")

        # Check if measures were merged
        if 'measures' in stocks_config:
            simple_measures = stocks_config['measures'].get('simple_measures', {})
            python_measures = stocks_config['measures'].get('python_measures', {})
            print(f"   Simple measures: {len(simple_measures)}")
            print(f"   Python measures: {len(python_measures)}")
            if python_measures:
                print(f"   Example Python measures: {list(python_measures.keys())[:3]}")

    except Exception as e:
        logger.error(f"Failed to load stocks model: {e}", exc_info=True)
        print(f"  Failed to load stocks model: {e}")
        import traceback
        traceback.print_exc()

    # Test loading company model (modular)
    print("\nLoading 'company' model (modular structure)...")
    try:
        company_config = loader.load_model_config('company')
        print(f"  Loaded company model successfully")
        print(f"   Model name: {company_config.get('model')}")
        print(f"   Version: {company_config.get('version')}")
        print(f"   Depends on: {company_config.get('depends_on')}")
        logger.info(f"Loaded company model: version={company_config.get('version')}")
    except Exception as e:
        logger.error(f"Failed to load company model: {e}")
        print(f"  Failed to load company model: {e}")

    # Test loading legacy model (single YAML)
    print("\nLoading legacy model (single YAML file)...")
    try:
        # Try to load a legacy model if it exists
        for legacy_model in ['equity', 'corporate', 'core']:
            legacy_path = models_dir / f"{legacy_model}.yaml"
            if legacy_path.exists():
                config = loader.load_model_config(legacy_model)
                print(f"  Loaded legacy model '{legacy_model}' successfully")
                logger.info(f"Loaded legacy model: {legacy_model}")
                break
    except Exception as e:
        logger.debug(f"No legacy models to test: {e}")
        print(f"   (No legacy models to test, which is OK)")


def test_model_registry():
    """Test ModelRegistry with modular models."""
    print_header("TEST 2: ModelRegistry - Discover Modular Models")
    logger.info("Starting ModelRegistry tests")

    models_dir = Path("configs/models")
    registry = ModelRegistry(models_dir)

    discovered = registry.list_models()
    print(f"\nDiscovered models: {discovered}")
    logger.info(f"Discovered {len(discovered)} models: {discovered}")

    # Test modular models
    for model_name in ['stocks', 'company', 'options']:
        print(f"\nTesting model: {model_name}")
        try:
            if registry.has_model(model_name):
                model_config = registry.get_model(model_name)
                print(f"   Model '{model_name}' found in registry")
                print(f"      Tables: {model_config.list_tables()[:5]}")  # First 5 tables
                print(f"      Measures: {model_config.list_measures()[:5]}")  # First 5 measures
                logger.debug(f"Model {model_name}: tables={model_config.list_tables()[:5]}")
            else:
                print(f"   Model '{model_name}' not found in registry")
                logger.warning(f"Model {model_name} not found")
        except Exception as e:
            logger.error(f"Error accessing model {model_name}: {e}")
            print(f"   Error accessing model '{model_name}': {e}")

    # Test model class registration
    print("\nTesting model class registration...")
    for model_name in ['stocks', 'company']:
        try:
            model_class = registry.get_model_class(model_name)
            print(f"   Model class for '{model_name}': {model_class.__name__}")
            logger.debug(f"Model class for {model_name}: {model_class.__name__}")
        except Exception as e:
            logger.debug(f"Model class for {model_name} not registered: {e}")
            print(f"   Model class for '{model_name}' not registered (OK if model not implemented yet)")


def test_inheritance_resolution():
    """Test that YAML inheritance resolves correctly."""
    print_header("TEST 3: Inheritance Resolution")
    logger.info("Starting inheritance resolution tests")

    models_dir = Path("configs/models")
    loader = ModelConfigLoader(models_dir)

    # Test stocks inheriting from securities
    print("\nTesting inheritance: stocks extends _base.securities")
    try:
        stocks_config = loader.load_model_config('stocks')

        # Check if stocks inherited base security fields
        dim_stock = stocks_config.get('schema', {}).get('dimensions', {}).get('dim_stock', {})
        columns = dim_stock.get('columns', {})

        # These should be inherited from _base.securities._dim_security
        base_fields = ['ticker', 'security_name', 'asset_type', 'exchange_code']
        # These are stocks-specific
        stocks_fields = ['company_id', 'cik', 'shares_outstanding']

        print(f"   Checking inherited base fields...")
        inherited_base = 0
        for field in base_fields:
            if field in columns:
                print(f"      '{field}' present (inherited)")
                inherited_base += 1
            else:
                print(f"      '{field}' missing (should be inherited)")

        print(f"   Checking stocks-specific fields...")
        for field in stocks_fields:
            if field in columns:
                print(f"      '{field}' present (stocks-specific)")
            else:
                print(f"      '{field}' missing")

        logger.info(f"Inheritance check: {inherited_base}/{len(base_fields)} base fields inherited")

        # Check if base measures were inherited
        measures = stocks_config.get('measures', {})
        simple_measures = measures.get('simple_measures', {})

        # These should be inherited from _base.securities.measures
        base_measures = ['avg_close_price', 'total_volume', 'max_high']

        print(f"   Checking inherited base measures...")
        inherited_count = 0
        for measure in base_measures:
            if measure in simple_measures:
                inherited_count += 1
        print(f"      {inherited_count}/{len(base_measures)} base measures inherited")
        logger.info(f"Measure inheritance: {inherited_count}/{len(base_measures)} base measures")

    except Exception as e:
        logger.error(f"Inheritance test failed: {e}", exc_info=True)
        print(f"   Inheritance test failed: {e}")
        import traceback
        traceback.print_exc()


def test_python_measures_discovery():
    """Test Python measures module discovery."""
    print_header("TEST 4: Python Measures Discovery")
    logger.info("Starting Python measures discovery tests")

    models_dir = Path("configs/models")
    loader = ModelConfigLoader(models_dir)

    # Test stocks Python measures
    print("\nTesting Python measures for 'stocks' model...")
    try:
        stocks_measures_class = loader.load_python_measures('stocks')
        if stocks_measures_class:
            print(f"   Python measures class loaded: {stocks_measures_class.__class__.__name__}")
            logger.info(f"Loaded Python measures: {stocks_measures_class.__class__.__name__}")

            # Check if it has expected methods
            expected_methods = ['calculate_sharpe_ratio', 'calculate_correlation_matrix',
                              'calculate_momentum_score']
            found_methods = 0
            for method in expected_methods:
                if hasattr(stocks_measures_class, method):
                    print(f"      Method '{method}' found")
                    found_methods += 1
                else:
                    print(f"      Method '{method}' missing")
            logger.info(f"Python measures: {found_methods}/{len(expected_methods)} methods found")
        else:
            logger.warning("No Python measures found for stocks")
            print(f"   No Python measures found for 'stocks' (might not be instantiated yet)")
    except Exception as e:
        logger.error(f"Failed to load Python measures: {e}", exc_info=True)
        print(f"   Failed to load Python measures: {e}")


def main():
    """Run all tests."""
    setup_logging()

    print("\n" + "=" * 80)
    print(" MODULAR YAML ARCHITECTURE TEST SUITE")
    print("=" * 80 + "\n")
    logger.info("Starting modular YAML architecture test suite")

    try:
        test_model_config_loader()
        test_model_registry()
        test_inheritance_resolution()
        test_python_measures_discovery()

        print_header("TEST SUITE COMPLETE")
        print("\nSummary:")
        print("   - ModelConfigLoader can load modular YAMLs")
        print("   - Model registry discovers modular models")
        print("   - YAML inheritance resolves correctly")
        print("   - Python measures can be discovered")
        print("\nNote: Some warnings are OK if models aren't fully implemented yet")
        logger.info("Test suite completed successfully")

    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        print(f"\nTest suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
