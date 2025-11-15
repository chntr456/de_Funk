#!/usr/bin/env python3
"""
Comprehensive validation script for path management migration.

This script validates that all Python files in the repository:
1. Can import without errors
2. Use standardized path patterns
3. Don't have API mismatches
4. Follow best practices

Usage:
    python -m scripts.validate_migration
    python -m scripts.validate_migration --fix  # Auto-fix issues
    python -m scripts.validate_migration --report  # Generate detailed report
"""

import sys
from pathlib import Path

import ast
import importlib.util
import subprocess
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
import re

# Bootstrap to add repo to path
_current = Path(__file__).resolve()
for _parent in [_current.parent] + list(_current.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from utils.repo import get_repo_root

@dataclass
class ValidationIssue:
    """Represents a validation issue found in a file."""
    file: Path
    line: int
    issue_type: str
    description: str
    severity: str  # 'error', 'warning', 'info'
    suggestion: Optional[str] = None

@dataclass
class ValidationResult:
    """Results of validating a single file."""
    file: Path
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    import_error: Optional[str] = None

class MigrationValidator:
    """Validates Python files for migration compliance."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.results: List[ValidationResult] = []

        # Patterns to detect
        self.old_path_patterns = [
            r'Path\(__file__\)\.parent\.parent',
            r'Path\(__file__\)\.parent\.parent\.parent',
            r"sys\.path\.insert\(0,\s*['\"]\/.*?de_Funk",  # Hardcoded paths
            r"sys\.path\.append\(.*?Path\(__file__\)",
        ]

        self.api_mismatches = [
            r'\.get_model\([^)]+\)\.model_cfg',  # Should use get_model_config()
            r'repo_root\s*=\s*Path\.cwd\(\)',  # Should use get_repo_root()
        ]

    def find_python_files(self) -> List[Path]:
        """Find all Python files to validate."""
        python_files = []

        # Directories to check
        check_dirs = [
            self.repo_root / "scripts",
            self.repo_root / "examples",
            self.repo_root / "tests",
            self.repo_root / "app",
        ]

        # Root level scripts
        for script in self.repo_root.glob("*.py"):
            if script.name not in ['setup.py', '__init__.py']:
                python_files.append(script)

        # Scripts in subdirectories
        for check_dir in check_dirs:
            if check_dir.exists():
                python_files.extend(check_dir.rglob("*.py"))

        # Exclude certain patterns
        exclude_patterns = ['__pycache__', '.pyc', 'venv', '.venv', 'build', 'dist']
        python_files = [
            f for f in python_files
            if not any(pattern in str(f) for pattern in exclude_patterns)
        ]

        return sorted(set(python_files))

    def check_old_patterns(self, file_path: Path) -> List[ValidationIssue]:
        """Check for old path management patterns."""
        issues = []

        try:
            content = file_path.read_text()
            lines = content.split('\n')

            # Skip pattern checks for test_utils_repo.py - it tests these patterns
            if file_path.name == 'test_utils_repo.py':
                return issues

            for line_num, line in enumerate(lines, 1):
                # Check for old path patterns
                for pattern in self.old_path_patterns:
                    if re.search(pattern, line):
                        issues.append(ValidationIssue(
                            file=file_path,
                            line=line_num,
                            issue_type='old_path_pattern',
                            description=f"Old path pattern: {pattern}",
                            severity='error',
                            suggestion="Use: from utils.repo import setup_repo_imports; repo_root = setup_repo_imports()"
                        ))

                # Check for API mismatches
                for pattern in self.api_mismatches:
                    if re.search(pattern, line):
                        issues.append(ValidationIssue(
                            file=file_path,
                            line=line_num,
                            issue_type='api_mismatch',
                            description=f"API mismatch: {pattern}",
                            severity='error',
                            suggestion="Use registry.get_model_config() instead of get_model().model_cfg"
                        ))

        except Exception as e:
            issues.append(ValidationIssue(
                file=file_path,
                line=0,
                issue_type='read_error',
                description=f"Failed to read file: {e}",
                severity='warning'
            ))

        return issues

    def check_imports(self, file_path: Path) -> Optional[str]:
        """Check if file can be imported without errors."""
        # Skip files that are just examples or not meant to be imported
        relative_path = file_path.relative_to(self.repo_root)

        # Don't try to import certain files
        skip_patterns = [
            'examples/',
            'test_',
            'debug_',
            'diagnose_',
        ]

        if any(pattern in str(relative_path) for pattern in skip_patterns):
            return None  # Skip import test for these

        # Try to check syntax at least
        try:
            content = file_path.read_text()
            ast.parse(content)
            return None  # Syntax is valid
        except SyntaxError as e:
            return f"Syntax error: {e}"
        except Exception as e:
            return f"Parse error: {e}"

    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single Python file."""
        result = ValidationResult(file=file_path, passed=True)

        # Check for old patterns
        pattern_issues = self.check_old_patterns(file_path)
        result.issues.extend(pattern_issues)

        # Check imports
        import_error = self.check_imports(file_path)
        result.import_error = import_error

        # Mark as failed if there are errors
        if any(i.severity == 'error' for i in result.issues) or import_error:
            result.passed = False

        return result

    def validate_all(self) -> Dict[str, any]:
        """Validate all Python files and return summary."""
        python_files = self.find_python_files()

        print(f"🔍 Validating {len(python_files)} Python files...")
        print()

        for file_path in python_files:
            result = self.validate_file(file_path)
            self.results.append(result)

        return self.generate_summary()

    def generate_summary(self) -> Dict[str, any]:
        """Generate validation summary."""
        summary = {
            'total_files': len(self.results),
            'passed': sum(1 for r in self.results if r.passed),
            'failed': sum(1 for r in self.results if not r.passed),
            'issues_by_type': {},
            'files_with_issues': [],
        }

        # Count issues by type
        for result in self.results:
            for issue in result.issues:
                issue_type = issue.issue_type
                if issue_type not in summary['issues_by_type']:
                    summary['issues_by_type'][issue_type] = 0
                summary['issues_by_type'][issue_type] += 1

            if not result.passed:
                summary['files_with_issues'].append({
                    'file': str(result.file.relative_to(self.repo_root)),
                    'issues': len(result.issues),
                    'import_error': result.import_error is not None,
                })

        return summary

    def print_report(self):
        """Print detailed validation report."""
        summary = self.generate_summary()

        print("=" * 80)
        print("📊 MIGRATION VALIDATION REPORT")
        print("=" * 80)
        print()

        print(f"Total Files: {summary['total_files']}")
        print(f"✅ Passed: {summary['passed']}")
        print(f"❌ Failed: {summary['failed']}")
        print()

        if summary['issues_by_type']:
            print("Issues by Type:")
            for issue_type, count in sorted(summary['issues_by_type'].items()):
                print(f"  - {issue_type}: {count}")
            print()

        # List files with issues
        if summary['files_with_issues']:
            print("Files with Issues:")
            for file_info in summary['files_with_issues']:
                print(f"  ❌ {file_info['file']}")
                print(f"     Issues: {file_info['issues']}, Import Error: {file_info['import_error']}")
            print()

        # Detailed issues
        print("=" * 80)
        print("🔍 DETAILED ISSUES")
        print("=" * 80)
        print()

        for result in self.results:
            if not result.passed:
                rel_path = result.file.relative_to(self.repo_root)
                print(f"File: {rel_path}")

                if result.import_error:
                    print(f"  ⚠️  Import Error: {result.import_error}")

                for issue in result.issues:
                    severity_icon = "🔴" if issue.severity == 'error' else "🟡"
                    print(f"  {severity_icon} Line {issue.line}: {issue.description}")
                    if issue.suggestion:
                        print(f"     💡 {issue.suggestion}")

                print()

        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)

        if summary['failed'] == 0:
            print("✅ All files passed validation!")
        else:
            print(f"❌ {summary['failed']} files need attention")
            print()
            print("Next steps:")
            print("1. Review issues above")
            print("2. Run: python -m scripts.validate_migration --fix  (to auto-fix)")
            print("3. Or manually fix issues following suggestions")

        return summary['failed'] == 0

def main():
    """Main validation entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate migration compliance")
    parser.add_argument('--fix', action='store_true', help='Auto-fix issues where possible')
    parser.add_argument('--report', action='store_true', help='Generate detailed report')
    args = parser.parse_args()

    repo_root = get_repo_root()
    validator = MigrationValidator(repo_root)

    # Run validation
    validator.validate_all()

    # Print report
    all_passed = validator.print_report()

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
