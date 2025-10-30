#!/usr/bin/env python3
"""
Import Statement Update Script for de_Funk project.

Updates all import statements to reflect the new directory structure.

USAGE:
  python update_imports.py --dry-run    # Preview changes
  python update_imports.py              # Execute updates

This script should be run AFTER migrate_structure.py
"""

import re
from pathlib import Path
from typing import Dict, List, Tuple
import argparse


class ImportUpdater:
    """Updates import statements across the codebase."""

    # Map old import paths to new import paths
    IMPORT_MAP = {
        # Core
        "src.core.connection": "core.connection",
        "src.core.duckdb_connection": "core.duckdb_connection",
        "src.core.spark_connection": "core.spark_connection",
        "src.core.connection_factory": "core.connection_factory",
        "src.core.model_registry": "models.registry",
        "src.orchestration.context": "core.context",

        # Models
        "src.model.silver": "models.builders",
        "src.model.loaders": "models.loaders",
        "src.model.api": "models.api",

        # Data pipelines
        "src.ingest": "datapipelines.ingestors",
        "src.data_pipelines.facets": "datapipelines.facets",
        "src.data_pipelines.polygon.facets": "datapipelines.facets.polygon",
        "src.data_pipelines.base_pipeline": "datapipelines.base",

        # App - Notebook
        "src.notebook.schema": "app.notebook.schema",
        "src.notebook.parser": "app.notebook.parser",
        "src.notebook.api": "app.notebook.api",
        "src.notebook.filters": "app.notebook.filters",
        "src.notebook.exhibits": "app.notebook.exhibits",

        # App - UI
        "src.ui": "app.ui",

        # App - Services
        "src.services": "app.services",

        # Orchestration
        "src.common": "orchestration.common",
        "src.orchestration": "orchestration",
    }

    def __init__(self, root_dir: str, dry_run: bool = False):
        self.root = Path(root_dir)
        self.dry_run = dry_run
        self.changes: List[Tuple[Path, int]] = []  # (file, num_changes)

    def log(self, message: str):
        """Log update step."""
        prefix = "[DRY RUN] " if self.dry_run else "[EXECUTE] "
        print(f"{prefix}{message}")

    def update_file(self, file_path: Path) -> int:
        """Update imports in a single file. Returns number of changes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            changes = 0

            # Update each import mapping
            for old_import, new_import in self.IMPORT_MAP.items():
                # Pattern 1: from src.X import Y
                pattern1 = rf'\bfrom {re.escape(old_import)}\b'
                if re.search(pattern1, content):
                    content = re.sub(pattern1, f'from {new_import}', content)
                    changes += len(re.findall(pattern1, original_content))

                # Pattern 2: import src.X
                pattern2 = rf'\bimport {re.escape(old_import)}\b'
                if re.search(pattern2, content):
                    content = re.sub(pattern2, f'import {new_import}', content)
                    changes += len(re.findall(pattern2, original_content))

                # Pattern 3: from src.X.Y import Z (partial match)
                # This catches longer paths that start with our mapping
                escaped_import = re.escape(old_import)
                pattern3 = rf'\bfrom {escaped_import}\.(\w+)'
                matches = re.finditer(pattern3, content)
                for match in matches:
                    old_full = f"{old_import}.{match.group(1)}"
                    new_full = f"{new_import}.{match.group(1)}"
                    content = content.replace(f"from {old_full}", f"from {new_full}")
                    changes += 1

            # Write back if changes were made
            if changes > 0 and content != original_content:
                if not self.dry_run:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                self.log(f"✓ Updated {file_path.relative_to(self.root)} ({changes} changes)")
                return changes

            return 0

        except Exception as e:
            self.log(f"✗ Error updating {file_path}: {e}")
            return 0

    def find_python_files(self) -> List[Path]:
        """Find all Python files in the project."""
        python_files = []

        # Search in new directories
        search_dirs = [
            "core",
            "models",
            "datapipelines",
            "orchestration",
            "app",
            "configs",  # YAML files might have Python code
            "tests",
        ]

        for dir_name in search_dirs:
            dir_path = self.root / dir_name
            if dir_path.exists():
                python_files.extend(dir_path.rglob("*.py"))

        # Also check root level
        python_files.extend(self.root.glob("*.py"))

        return [f for f in python_files if "__pycache__" not in str(f)]

    def run_update(self):
        """Execute the full import update."""
        self.log("=" * 60)
        self.log("Starting Import Statement Updates")
        self.log("=" * 60)

        # Find all Python files
        self.log("\n🔍 Finding Python files...")
        python_files = self.find_python_files()
        self.log(f"Found {len(python_files)} Python files")

        # Update each file
        self.log("\n📝 Updating imports...")
        total_changes = 0
        files_changed = 0

        for file_path in python_files:
            changes = self.update_file(file_path)
            if changes > 0:
                total_changes += changes
                files_changed += 1
                self.changes.append((file_path, changes))

        # Summary
        self.log("\n" + "=" * 60)
        self.log(f"Import update {'would be' if self.dry_run else 'completed'} successfully!")
        self.log(f"Files changed: {files_changed}/{len(python_files)}")
        self.log(f"Total import changes: {total_changes}")
        self.log("=" * 60)

        if self.dry_run:
            self.log("\n⚠️  This was a DRY RUN. No changes were made.")
            self.log("Run without --dry-run to execute the updates.")
        else:
            self.log("\n✅ Next steps:")
            self.log("1. Test the application: python -m app.ui.notebook_app_duckdb")
            self.log("2. Run tests: pytest tests/")
            self.log("3. Commit changes: git add . && git commit -m 'Update imports for new structure'")

        # Show top files with most changes
        if self.changes:
            self.log("\n📊 Files with most changes:")
            sorted_changes = sorted(self.changes, key=lambda x: x[1], reverse=True)
            for file_path, num_changes in sorted_changes[:10]:
                self.log(f"  {file_path.relative_to(self.root)}: {num_changes} changes")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Update imports for new de_Funk project structure"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without executing"
    )
    parser.add_argument(
        "--root",
        type=str,
        default="/home/user/de_Funk",
        help="Project root directory"
    )

    args = parser.parse_args()

    # Run update
    updater = ImportUpdater(args.root, dry_run=args.dry_run)
    updater.run_update()

    return 0


if __name__ == "__main__":
    exit(main())
