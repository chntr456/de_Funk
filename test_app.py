#!/usr/bin/env python3
"""
Testing Script for de_Funk Application

Tests the reorganized project structure to ensure:
- All imports work correctly
- Core connections initialize
- Models load properly
- UI components are accessible
- Services function correctly

USAGE:
  python test_app.py              # Run all tests
  python test_app.py --quick      # Run quick imports-only test
  python test_app.py --verbose    # Verbose output
"""

import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Callable

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class TestResult:
    """Tracks test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.tests: List[Tuple[str, bool, str]] = []

    def add(self, name: str, success: bool, message: str = ""):
        """Add test result."""
        if success:
            self.passed += 1
        else:
            self.failed += 1
        self.tests.append((name, success, message))

    def add_warning(self, name: str, message: str):
        """Add warning."""
        self.warnings += 1
        self.tests.append((name, None, message))

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 70)
        print(f"{Colors.BOLD}TEST SUMMARY{Colors.END}")
        print("=" * 70)

        for name, success, message in self.tests:
            if success is None:  # Warning
                icon = f"{Colors.YELLOW}⚠{Colors.END}"
                status = f"{Colors.YELLOW}WARNING{Colors.END}"
            elif success:
                icon = f"{Colors.GREEN}✓{Colors.END}"
                status = f"{Colors.GREEN}PASS{Colors.END}"
            else:
                icon = f"{Colors.RED}✗{Colors.END}"
                status = f"{Colors.RED}FAIL{Colors.END}"

            print(f"{icon} {name:.<50} {status}")
            if message and not success:
                print(f"   └─ {Colors.RED}{message}{Colors.END}")
            elif message and success is None:
                print(f"   └─ {Colors.YELLOW}{message}{Colors.END}")

        print("\n" + "=" * 70)
        total = self.passed + self.failed
        print(f"Total: {total} | ", end="")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.END} | ", end="")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.END} | ", end="")
        print(f"{Colors.YELLOW}Warnings: {self.warnings}{Colors.END}")
        print("=" * 70)

        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.END}\n")
            return 0
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ SOME TESTS FAILED{Colors.END}\n")
            return 1


class AppTester:
    """Tests the de_Funk application."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = TestResult()

    def log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"{Colors.BLUE}ℹ{Colors.END} {message}")

    def test_import(self, name: str, import_fn: Callable) -> bool:
        """Test a single import."""
        try:
            import_fn()
            self.log(f"Import successful: {name}")
            return True
        except Exception as e:
            self.log(f"Import failed: {name} - {str(e)}")
            return False

    def test_core_imports(self):
        """Test core package imports."""
        print(f"\n{Colors.BOLD}Testing core/ imports...{Colors.END}")

        tests = [
            ("core.connection", lambda: __import__('core.connection', fromlist=['DataConnection'])),
            ("core.duckdb_connection", lambda: __import__('core.duckdb_connection', fromlist=['DuckDBConnection'])),
            ("core.context", lambda: __import__('core.context', fromlist=['RepoContext'])),
            ("core.validation", lambda: __import__('core.validation', fromlist=[''])),
        ]

        for name, import_fn in tests:
            success = self.test_import(name, import_fn)
            self.results.add(f"Import {name}", success, "" if success else "Module not found or has errors")

    def test_models_imports(self):
        """Test models package imports."""
        print(f"\n{Colors.BOLD}Testing models/ imports...{Colors.END}")

        tests = [
            ("models.registry", lambda: __import__('models.registry', fromlist=['ModelRegistry'])),
            ("models.loaders.parquet_loader", lambda: __import__('models.loaders.parquet_loader', fromlist=['ParquetLoader'])),
            ("models.loaders.parquet_loader_optimized", lambda: __import__('models.loaders.parquet_loader_optimized', fromlist=['ParquetLoaderOptimized'])),
            ("models.builders.company_silver_builder", lambda: __import__('models.builders.company_silver_builder', fromlist=[''])),
            ("models.api.session", lambda: __import__('models.api.session', fromlist=[''])),
        ]

        for name, import_fn in tests:
            success = self.test_import(name, import_fn)
            self.results.add(f"Import {name}", success, "" if success else "Module not found or has errors")

    def test_datapipelines_imports(self):
        """Test datapipelines package imports."""
        print(f"\n{Colors.BOLD}Testing datapipelines/ imports...{Colors.END}")

        tests = [
            ("datapipelines.ingestors.base_ingestor", lambda: __import__('datapipelines.ingestors.base_ingestor', fromlist=[''])),
            ("datapipelines.facets.base_facet", lambda: __import__('datapipelines.facets.base_facet', fromlist=[''])),
            ("datapipelines.base.http_client", lambda: __import__('datapipelines.base.http_client', fromlist=[''])),
        ]

        for name, import_fn in tests:
            success = self.test_import(name, import_fn)
            self.results.add(f"Import {name}", success, "" if success else "Module not found or has errors")

    def test_app_imports(self):
        """Test app package imports."""
        print(f"\n{Colors.BOLD}Testing app/ imports...{Colors.END}")

        tests = [
            ("app.notebook.schema", lambda: __import__('app.notebook.schema', fromlist=['NotebookConfig'])),
            ("app.notebook.parser", lambda: __import__('app.notebook.parser', fromlist=['NotebookParser'])),
            ("app.notebook.api.notebook_session", lambda: __import__('app.notebook.api.notebook_session', fromlist=['NotebookSession'])),
            ("app.services.storage_service", lambda: __import__('app.services.storage_service', fromlist=['SilverStorageService'])),
            ("app.ui.components.filters", lambda: __import__('app.ui.components.filters', fromlist=['render_filters_section'])),
            ("app.ui.components.sidebar", lambda: __import__('app.ui.components.sidebar', fromlist=[''])),
        ]

        for name, import_fn in tests:
            success = self.test_import(name, import_fn)
            self.results.add(f"Import {name}", success, "" if success else "Module not found or has errors")

    def test_orchestration_imports(self):
        """Test orchestration package imports."""
        print(f"\n{Colors.BOLD}Testing orchestration/ imports...{Colors.END}")

        tests = [
            ("orchestration.common.path_utils", lambda: __import__('orchestration.common.path_utils', fromlist=[''])),
            ("orchestration.orchestrator", lambda: __import__('orchestration.orchestrator', fromlist=[''])),
        ]

        for name, import_fn in tests:
            success = self.test_import(name, import_fn)
            self.results.add(f"Import {name}", success, "" if success else "Module not found or has errors")

    def test_duckdb_connection(self):
        """Test DuckDB connection initialization."""
        print(f"\n{Colors.BOLD}Testing DuckDB connection...{Colors.END}")

        try:
            from core.duckdb_connection import DuckDBConnection
            conn = DuckDBConnection(db_path=":memory:")
            self.log("DuckDB connection created successfully")

            # Test basic query
            result = conn.execute_sql("SELECT 1 as test")
            self.log("Basic DuckDB query executed")

            conn.stop()
            self.log("DuckDB connection closed")

            self.results.add("DuckDB Connection", True)
        except Exception as e:
            self.results.add("DuckDB Connection", False, str(e))

    def test_repo_context(self):
        """Test RepoContext initialization."""
        print(f"\n{Colors.BOLD}Testing RepoContext...{Colors.END}")

        try:
            from core.context import RepoContext
            from pathlib import Path

            repo_root = Path(__file__).parent
            ctx = RepoContext.from_repo_root(connection_type="duckdb")

            self.log(f"RepoContext initialized with connection type: duckdb")
            self.log(f"Repo root: {ctx.repo}")

            # Check if connection exists
            if ctx.connection is not None:
                self.log("Connection object created")
                self.results.add("RepoContext Initialization", True)
            else:
                self.results.add("RepoContext Initialization", False, "Connection is None")

            # Cleanup
            if hasattr(ctx, 'connection') and ctx.connection:
                ctx.connection.stop()

        except Exception as e:
            self.results.add("RepoContext Initialization", False, str(e))

    def test_model_registry(self):
        """Test ModelRegistry."""
        print(f"\n{Colors.BOLD}Testing ModelRegistry...{Colors.END}")

        try:
            from models.registry import ModelRegistry
            from pathlib import Path

            models_dir = Path(__file__).parent / "configs" / "models"

            if not models_dir.exists():
                self.results.add_warning("ModelRegistry", f"Models directory not found: {models_dir}")
                return

            registry = ModelRegistry(models_dir)
            self.log(f"ModelRegistry initialized with path: {models_dir}")

            # Try to list models
            models = registry.list_models()
            self.log(f"Found {len(models)} models: {models}")

            self.results.add("ModelRegistry", True)

        except Exception as e:
            self.results.add("ModelRegistry", False, str(e))

    def test_notebook_parser(self):
        """Test NotebookParser."""
        print(f"\n{Colors.BOLD}Testing NotebookParser...{Colors.END}")

        try:
            from app.notebook.parser import NotebookParser
            from pathlib import Path

            repo_root = Path(__file__).parent
            parser = NotebookParser(repo_root)

            self.log(f"NotebookParser initialized")

            # Try to find a notebook to parse
            notebooks_dir = repo_root / "configs" / "notebooks"
            if notebooks_dir.exists():
                # Find first .yaml file
                notebooks = list(notebooks_dir.rglob("*.yaml"))
                if notebooks:
                    test_notebook = notebooks[0]
                    self.log(f"Testing with notebook: {test_notebook.name}")

                    config = parser.parse_file(str(test_notebook))
                    self.log(f"Parsed notebook: {config.notebook.title}")

                    self.results.add("NotebookParser", True)
                else:
                    self.results.add_warning("NotebookParser", "No notebooks found to test parsing")
            else:
                self.results.add_warning("NotebookParser", f"Notebooks directory not found: {notebooks_dir}")

        except Exception as e:
            self.results.add("NotebookParser", False, str(e))

    def test_storage_service(self):
        """Test StorageService."""
        print(f"\n{Colors.BOLD}Testing StorageService...{Colors.END}")

        try:
            from app.services.storage_service import SilverStorageService
            from core.duckdb_connection import DuckDBConnection
            from models.registry import ModelRegistry
            from pathlib import Path

            # Initialize dependencies
            conn = DuckDBConnection(db_path=":memory:")
            models_dir = Path(__file__).parent / "configs" / "models"

            if not models_dir.exists():
                self.results.add_warning("StorageService", f"Models directory not found: {models_dir}")
                conn.stop()
                return

            registry = ModelRegistry(models_dir)
            service = SilverStorageService(conn, registry)

            self.log("StorageService initialized")

            # List available models
            models = service.list_models()
            self.log(f"Available models: {models}")

            self.results.add("StorageService", True)

            # Cleanup
            conn.stop()

        except Exception as e:
            self.results.add("StorageService", False, str(e))

    def test_ui_components(self):
        """Test UI components can be imported."""
        print(f"\n{Colors.BOLD}Testing UI components...{Colors.END}")

        tests = [
            ("Line Chart Exhibit", lambda: __import__('app.ui.components.exhibits.line_chart', fromlist=['render_line_chart'])),
            ("Bar Chart Exhibit", lambda: __import__('app.ui.components.exhibits.bar_chart', fromlist=['render_bar_chart'])),
            ("Metric Cards Exhibit", lambda: __import__('app.ui.components.exhibits.metric_cards', fromlist=['render_metric_cards'])),
            ("Data Table Exhibit", lambda: __import__('app.ui.components.exhibits.data_table', fromlist=['render_data_table'])),
            ("Theme", lambda: __import__('app.ui.components.theme', fromlist=['apply_professional_theme'])),
        ]

        for name, import_fn in tests:
            success = self.test_import(name, import_fn)
            self.results.add(f"UI Component: {name}", success, "" if success else "Module not found or has errors")

    def test_directory_structure(self):
        """Verify directory structure."""
        print(f"\n{Colors.BOLD}Testing directory structure...{Colors.END}")

        root = Path(__file__).parent
        expected_dirs = [
            "core",
            "models",
            "models/builders",
            "models/loaders",
            "models/base",
            "models/measures",
            "models/api",
            "datapipelines",
            "datapipelines/ingestors",
            "datapipelines/facets",
            "datapipelines/cleaners",
            "datapipelines/schemas",
            "orchestration",
            "orchestration/pipelines",
            "orchestration/tasks",
            "app",
            "app/notebook",
            "app/ui",
            "app/services",
            "configs",
            "storage",
        ]

        for dir_path in expected_dirs:
            full_path = root / dir_path
            exists = full_path.exists() and full_path.is_dir()
            if not exists:
                self.results.add(f"Directory: {dir_path}", False, "Directory not found")
            else:
                self.log(f"Directory exists: {dir_path}")

        # Count as one test
        missing = sum(1 for d in expected_dirs if not (root / d).exists())
        if missing == 0:
            self.results.add("Directory Structure", True)
        else:
            self.results.add("Directory Structure", False, f"{missing} directories missing")

    def run_all_tests(self, quick: bool = False):
        """Run all tests."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}de_Funk Application Test Suite{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")

        # Always test directory structure first
        self.test_directory_structure()

        # Test all imports
        self.test_core_imports()
        self.test_models_imports()
        self.test_datapipelines_imports()
        self.test_app_imports()
        self.test_orchestration_imports()

        if not quick:
            # Test functionality
            self.test_duckdb_connection()
            self.test_repo_context()
            self.test_model_registry()
            self.test_notebook_parser()
            self.test_storage_service()
            self.test_ui_components()

        # Print summary
        return self.results.print_summary()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test de_Funk application structure and functionality"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick imports-only test"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Run tests
    tester = AppTester(verbose=args.verbose)
    exit_code = tester.run_all_tests(quick=args.quick)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
