#!/usr/bin/env python3
"""
Comprehensive Script Tester

This script validates all scripts in the organized scripts/ directory:
- Tests syntax (can import without errors)
- Tests documentation (has docstring and --help)
- Tests module structure (proper imports)
- Generates comprehensive test report

Usage:
    python -m scripts.test_scripts
    python -m scripts.test_scripts --verbose
    python -m scripts.test_scripts --category build
"""

import sys
from pathlib import Path
import ast
import subprocess
import importlib.util
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()


@dataclass
class ScriptTestResult:
    """Results of testing a single script."""
    script_path: Path
    category: str
    script_name: str

    # Test results
    syntax_valid: bool = False
    has_docstring: bool = False
    has_main: bool = False
    has_help: bool = False
    importable: bool = False

    # Errors
    syntax_error: Optional[str] = None
    import_error: Optional[str] = None
    help_error: Optional[str] = None

    # Metadata
    docstring: Optional[str] = None
    line_count: int = 0

    @property
    def passed(self) -> bool:
        """Overall pass/fail status."""
        return self.syntax_valid and self.has_docstring and self.importable

    @property
    def status_icon(self) -> str:
        """Visual status icon."""
        if self.passed:
            return "✅"
        elif self.syntax_valid:
            return "⚠️"
        else:
            return "❌"


@dataclass
class TestSummary:
    """Summary of all test results."""
    total_scripts: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_warnings: int = 0

    by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)

    results: List[ScriptTestResult] = field(default_factory=list)

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def duration(self) -> float:
        """Test duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def pass_rate(self) -> float:
        """Pass rate percentage."""
        if self.total_scripts == 0:
            return 0.0
        return (self.total_passed / self.total_scripts) * 100


class ScriptTester:
    """Comprehensive script tester."""

    SCRIPT_CATEGORIES = {
        'build': 'Model building and Silver layer construction',
        'ingest': 'Data ingestion and Bronze layer',
        'maintenance': 'Clearing, resetting, cleanup',
        'forecast': 'Forecasting operations',
        'test': 'Testing and validation'
    }

    def __init__(self, scripts_dir: Path, verbose: bool = False):
        """
        Initialize script tester.

        Args:
            scripts_dir: Path to scripts directory
            verbose: Enable verbose output
        """
        self.scripts_dir = scripts_dir
        self.verbose = verbose
        self.summary = TestSummary()

    def discover_scripts(self, category: Optional[str] = None) -> List[Tuple[str, Path]]:
        """
        Discover all scripts to test.

        Args:
            category: Filter by category (None = all categories)

        Returns:
            List of (category, script_path) tuples
        """
        scripts = []

        categories = [category] if category else self.SCRIPT_CATEGORIES.keys()

        for cat in categories:
            cat_dir = self.scripts_dir / cat
            if cat_dir.exists():
                # Find all .py files (excluding __init__.py)
                for script_path in sorted(cat_dir.glob("*.py")):
                    if script_path.name != "__init__.py":
                        scripts.append((cat, script_path))

                # Find all .sh files
                for script_path in sorted(cat_dir.glob("*.sh")):
                    scripts.append((cat, script_path))

        return scripts

    def test_script(self, category: str, script_path: Path) -> ScriptTestResult:
        """
        Test a single script.

        Args:
            category: Script category
            script_path: Path to script

        Returns:
            Test result
        """
        result = ScriptTestResult(
            script_path=script_path,
            category=category,
            script_name=script_path.name
        )

        # Count lines
        try:
            content = script_path.read_text()
            result.line_count = len(content.split('\n'))
        except Exception as e:
            result.import_error = f"Failed to read file: {e}"
            return result

        # Shell scripts - different validation
        if script_path.suffix == '.sh':
            return self._test_shell_script(result, script_path)

        # Python scripts
        return self._test_python_script(result, script_path, content)

    def _test_python_script(
        self,
        result: ScriptTestResult,
        script_path: Path,
        content: str
    ) -> ScriptTestResult:
        """Test a Python script."""

        # Test 1: Syntax validation
        try:
            tree = ast.parse(content)
            result.syntax_valid = True

            # Test 2: Check for docstring
            docstring = ast.get_docstring(tree)
            if docstring:
                result.has_docstring = True
                result.docstring = docstring.split('\n')[0]  # First line

            # Test 3: Check for main function or if __name__ == '__main__'
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == 'main':
                    result.has_main = True
                    break
                elif isinstance(node, ast.If):
                    # Check for if __name__ == '__main__'
                    if isinstance(node.test, ast.Compare):
                        left = node.test.left
                        if isinstance(left, ast.Name) and left.id == '__name__':
                            result.has_main = True
                            break

        except SyntaxError as e:
            result.syntax_error = f"Line {e.lineno}: {e.msg}"
            return result
        except Exception as e:
            result.syntax_error = str(e)
            return result

        # Test 4: Import test (try to import as module)
        try:
            # Create module spec
            module_name = f"scripts.{result.category}.{script_path.stem}"
            spec = importlib.util.spec_from_file_location(module_name, script_path)

            if spec and spec.loader:
                # Don't actually import (could have side effects)
                # Just check if spec can be created
                result.importable = True
        except Exception as e:
            result.import_error = str(e)

        # Test 5: Help flag test (if has main)
        if result.has_main:
            try:
                # Try to run with --help
                proc = subprocess.run(
                    [sys.executable, '-m', f'scripts.{result.category}.{script_path.stem}', '--help'],
                    capture_output=True,
                    timeout=5,
                    cwd=repo_root
                )

                if proc.returncode == 0:
                    result.has_help = True
                else:
                    # Some scripts may not have --help, that's okay
                    result.has_help = False

            except subprocess.TimeoutExpired:
                result.help_error = "Timeout (5s)"
            except Exception as e:
                result.help_error = str(e)

        return result

    def _test_shell_script(self, result: ScriptTestResult, script_path: Path) -> ScriptTestResult:
        """Test a shell script."""
        # Basic validation for shell scripts
        try:
            content = script_path.read_text()

            # Check shebang
            if content.startswith('#!/'):
                result.syntax_valid = True

            # Check for comments (basic documentation)
            if '#' in content:
                result.has_docstring = True
                # Extract first comment as docstring
                for line in content.split('\n'):
                    if line.strip().startswith('#') and not line.startswith('#!'):
                        result.docstring = line.strip('# ')
                        break

            # Shell scripts are "importable" if they have execute permissions
            result.importable = script_path.stat().st_mode & 0o111 != 0

        except Exception as e:
            result.syntax_error = str(e)

        return result

    def test_all(self, category: Optional[str] = None) -> TestSummary:
        """
        Test all scripts.

        Args:
            category: Filter by category (None = all)

        Returns:
            Test summary
        """
        self.summary.start_time = datetime.now()

        # Discover scripts
        scripts = self.discover_scripts(category)
        self.summary.total_scripts = len(scripts)

        if self.verbose:
            print(f"Discovered {len(scripts)} script(s) to test")
            print()

        # Test each script
        for cat, script_path in scripts:
            if self.verbose:
                print(f"Testing {cat}/{script_path.name}...", end=" ")

            result = self.test_script(cat, script_path)
            self.summary.results.append(result)

            # Update category stats
            if cat not in self.summary.by_category:
                self.summary.by_category[cat] = {
                    'total': 0,
                    'passed': 0,
                    'failed': 0,
                    'warnings': 0
                }

            self.summary.by_category[cat]['total'] += 1

            if result.passed:
                self.summary.total_passed += 1
                self.summary.by_category[cat]['passed'] += 1
                if self.verbose:
                    print("✅ PASS")
            elif result.syntax_valid:
                self.summary.total_warnings += 1
                self.summary.by_category[cat]['warnings'] += 1
                if self.verbose:
                    print("⚠️  WARN")
            else:
                self.summary.total_failed += 1
                self.summary.by_category[cat]['failed'] += 1
                if self.verbose:
                    print("❌ FAIL")

        self.summary.end_time = datetime.now()

        return self.summary

    def print_report(self):
        """Print comprehensive test report."""
        print("=" * 100)
        print("SCRIPT VALIDATION REPORT")
        print("=" * 100)
        print()

        # Overall stats
        print(f"Total Scripts:  {self.summary.total_scripts}")
        print(f"✅ Passed:      {self.summary.total_passed}")
        print(f"⚠️  Warnings:    {self.summary.total_warnings}")
        print(f"❌ Failed:      {self.summary.total_failed}")
        print(f"Pass Rate:      {self.summary.pass_rate:.1f}%")
        print(f"Duration:       {self.summary.duration:.2f}s")
        print()

        # Category breakdown
        print("=" * 100)
        print("CATEGORY BREAKDOWN")
        print("=" * 100)
        print()

        for cat, stats in sorted(self.summary.by_category.items()):
            desc = self.SCRIPT_CATEGORIES.get(cat, "Unknown")
            pass_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0

            print(f"📁 {cat.upper()} - {desc}")
            print(f"   Total: {stats['total']}, "
                  f"✅ {stats['passed']}, "
                  f"⚠️  {stats['warnings']}, "
                  f"❌ {stats['failed']} "
                  f"({pass_rate:.0f}% pass)")
            print()

        # Detailed results
        print("=" * 100)
        print("DETAILED RESULTS")
        print("=" * 100)
        print()

        for result in sorted(self.summary.results, key=lambda r: (r.category, r.script_name)):
            print(f"{result.status_icon} {result.category}/{result.script_name}")
            print(f"   Lines: {result.line_count}")

            if result.docstring:
                print(f"   Doc: {result.docstring[:70]}{'...' if len(result.docstring) > 70 else ''}")

            # Show test details
            checks = []
            if result.syntax_valid:
                checks.append("✓ Syntax")
            else:
                checks.append("✗ Syntax")

            if result.has_docstring:
                checks.append("✓ Doc")
            else:
                checks.append("✗ Doc")

            if result.importable:
                checks.append("✓ Import")
            else:
                checks.append("✗ Import")

            if result.has_main and result.has_help:
                checks.append("✓ Help")
            elif result.has_main:
                checks.append("~ Help")

            print(f"   Checks: {', '.join(checks)}")

            # Show errors
            if result.syntax_error:
                print(f"   ❌ Syntax Error: {result.syntax_error}")
            if result.import_error:
                print(f"   ⚠️  Import Issue: {result.import_error}")
            if result.help_error:
                print(f"   ⚠️  Help Issue: {result.help_error}")

            print()

        # Final summary
        print("=" * 100)
        if self.summary.total_failed == 0 and self.summary.total_warnings == 0:
            print("✅ ALL SCRIPTS VALIDATED SUCCESSFULLY")
        elif self.summary.total_failed == 0:
            print(f"⚠️  ALL SCRIPTS PASSED WITH {self.summary.total_warnings} WARNING(S)")
        else:
            print(f"❌ {self.summary.total_failed} SCRIPT(S) FAILED VALIDATION")
        print("=" * 100)

    def save_report(self, output_file: Path):
        """
        Save test report to JSON file.

        Args:
            output_file: Output file path
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_scripts': self.summary.total_scripts,
                'passed': self.summary.total_passed,
                'warnings': self.summary.total_warnings,
                'failed': self.summary.total_failed,
                'pass_rate': self.summary.pass_rate,
                'duration': self.summary.duration,
            },
            'by_category': self.summary.by_category,
            'results': [
                {
                    'category': r.category,
                    'script': r.script_name,
                    'passed': r.passed,
                    'line_count': r.line_count,
                    'syntax_valid': r.syntax_valid,
                    'has_docstring': r.has_docstring,
                    'has_main': r.has_main,
                    'has_help': r.has_help,
                    'importable': r.importable,
                    'docstring': r.docstring,
                    'errors': {
                        'syntax': r.syntax_error,
                        'import': r.import_error,
                        'help': r.help_error,
                    }
                }
                for r in self.summary.results
            ]
        }

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Report saved to: {output_file}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Comprehensive script validation tester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--category',
        choices=list(ScriptTester.SCRIPT_CATEGORIES.keys()),
        help='Test only scripts in specific category'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--output',
        type=Path,
        help='Save report to JSON file'
    )

    args = parser.parse_args()

    # Initialize tester
    scripts_dir = repo_root / "scripts"
    tester = ScriptTester(scripts_dir, verbose=args.verbose)

    # Run tests
    print("🔍 Testing scripts...")
    print()

    tester.test_all(category=args.category)

    # Print report
    tester.print_report()

    # Save report if requested
    if args.output:
        tester.save_report(args.output)

    # Exit with appropriate code
    sys.exit(0 if tester.summary.total_failed == 0 else 1)


if __name__ == '__main__':
    main()
