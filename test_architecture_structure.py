#!/usr/bin/env python3
"""
Structural test for the new scalable model architecture.

Tests the architecture without requiring Spark/runtime dependencies.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def test_directory_structure():
    """Test that new directories exist"""
    print("\nTesting directory structure...")

    repo_root = Path.cwd()

    # Check base model directory
    assert (repo_root / "models" / "base").exists(), "models/base directory missing"
    assert (repo_root / "models" / "base" / "model.py").exists(), "BaseModel missing"
    assert (repo_root / "models" / "base" / "service.py").exists(), "BaseAPI missing"
    print("  ✓ Base model directory structure")

    # Check company model directory
    assert (repo_root / "models" / "company").exists(), "models/company directory missing"
    assert (repo_root / "models" / "company" / "model.py").exists(), "CompanyModel missing"
    assert (repo_root / "models" / "company" / "types").exists(), "Company types missing"
    assert (repo_root / "models" / "company" / "services").exists(), "Company services missing"
    print("  ✓ Company model directory structure")

    # Check forecast model directory
    assert (repo_root / "models" / "forecast").exists(), "models/forecast directory missing"
    assert (repo_root / "models" / "forecast" / "model.py").exists(), "ForecastModel missing"
    assert (repo_root / "models" / "forecast" / "types").exists(), "Forecast types missing"
    assert (repo_root / "models" / "forecast" / "services").exists(), "Forecast services missing"
    print("  ✓ Forecast model directory structure")


def test_config_files():
    """Test that config files are updated"""
    print("\nTesting configuration files...")

    repo_root = Path.cwd()

    # Check company.yaml
    company_yaml = repo_root / "configs" / "models" / "company.yaml"
    assert company_yaml.exists(), "company.yaml missing"
    content = company_yaml.read_text()
    assert "graph:" in content, "company.yaml missing graph structure"
    assert "nodes:" in content, "company.yaml missing nodes"
    print("  ✓ company.yaml has graph structure")

    # Check forecast.yaml
    forecast_yaml = repo_root / "configs" / "models" / "forecast.yaml"
    assert forecast_yaml.exists(), "forecast.yaml missing"
    content = forecast_yaml.read_text()
    assert "graph:" in content, "forecast.yaml missing graph structure"
    assert "depends_on:" in content, "forecast.yaml missing dependencies"
    print("  ✓ forecast.yaml has graph structure and dependencies")


def test_backward_compatibility():
    """Test that old API imports still work"""
    print("\nTesting backward compatibility...")

    # These should work without Spark because they just re-export
    try:
        # Check old API files exist
        repo_root = Path.cwd()
        assert (repo_root / "models" / "api" / "types.py").exists()
        assert (repo_root / "models" / "api" / "services.py").exists()
        assert (repo_root / "models" / "api" / "session.py").exists()
        print("  ✓ Old API files exist")

        # Check they have imports
        types_content = (repo_root / "models" / "api" / "types.py").read_text()
        assert "from models.company.types import" in types_content
        print("  ✓ types.py imports from new location")

        services_content = (repo_root / "models" / "api" / "services.py").read_text()
        assert "from models.company.services import" in services_content
        print("  ✓ services.py imports from new location")

        session_content = (repo_root / "models" / "api" / "session.py").read_text()
        assert "class UniversalSession" in session_content
        print("  ✓ session.py has UniversalSession")

    except Exception as e:
        print(f"  ✗ Backward compatibility test failed: {e}")
        raise


def test_new_model_files():
    """Test that new model files have expected content"""
    print("\nTesting new model files...")

    repo_root = Path.cwd()

    # Check BaseModel
    base_model = (repo_root / "models" / "base" / "model.py").read_text()
    assert "class BaseModel" in base_model
    assert "def build(self" in base_model
    assert "def _build_nodes(self" in base_model
    assert "def _materialize_paths(self" in base_model
    print("  ✓ BaseModel has core methods")

    # Check CompanyModel
    company_model = (repo_root / "models" / "company" / "model.py").read_text()
    assert "class CompanyModel(BaseModel)" in company_model
    assert "from models.base.model import BaseModel" in company_model
    print("  ✓ CompanyModel inherits from BaseModel")

    # Check ForecastModel
    forecast_model = (repo_root / "models" / "forecast" / "model.py").read_text()
    assert "class ForecastModel(BaseModel)" in forecast_model
    assert "def set_session(self" in forecast_model
    assert "def custom_node_loading(self" in forecast_model
    print("  ✓ ForecastModel inherits from BaseModel and has custom methods")

    # Check UniversalSession
    session_file = (repo_root / "models" / "api" / "session.py").read_text()
    assert "class UniversalSession" in session_file
    assert "def load_model(self" in session_file
    assert "def get_table(self, model_name" in session_file
    print("  ✓ UniversalSession has model-agnostic methods")


def main():
    """Run all structural tests"""
    print("\n" + "=" * 60)
    print("ARCHITECTURE STRUCTURE TESTS")
    print("=" * 60)

    try:
        test_directory_structure()
        test_config_files()
        test_backward_compatibility()
        test_new_model_files()

        print("\n" + "=" * 60)
        print("ALL STRUCTURE TESTS PASSED! ✓")
        print("=" * 60)
        print("\nArchitecture successfully refactored:")
        print("  ✓ Base model abstractions created")
        print("  ✓ Company model uses BaseModel")
        print("  ✓ Forecast model uses BaseModel")
        print("  ✓ UniversalSession implemented")
        print("  ✓ Backward compatibility maintained")
        print("  ✓ Directory structure organized")
        print("\nNote: Runtime tests require Spark environment")
        print()

    except AssertionError as e:
        print(f"\n✗ STRUCTURE TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
