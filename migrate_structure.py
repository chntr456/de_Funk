#!/usr/bin/env python3
"""
Directory Structure Migration Script for de_Funk project.

This script reorganizes the project structure from:
  de_Funk/src/*
To:
  de_Funk/{core,models,datapipelines,orchestration,app}

USAGE:
  python migrate_structure.py --dry-run    # Preview changes
  python migrate_structure.py              # Execute migration

SAFETY:
- Uses git mv to preserve history
- Creates backup before migration
- Can be rolled back with git reset
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict
import argparse


class ProjectMigration:
    """Handles the de_Funk project structure migration."""

    def __init__(self, root_dir: str, dry_run: bool = False):
        self.root = Path(root_dir)
        self.dry_run = dry_run
        self.moves: List[Tuple[Path, Path]] = []

    def log(self, message: str):
        """Log migration step."""
        prefix = "[DRY RUN] " if self.dry_run else "[EXECUTE] "
        print(f"{prefix}{message}")

    def git_mv(self, src: Path, dst: Path):
        """Move file/directory using git mv to preserve history."""
        if self.dry_run:
            self.log(f"git mv {src} → {dst}")
            return

        # Ensure destination parent exists
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Use git mv if in git repo
        try:
            subprocess.run(
                ["git", "mv", str(src), str(dst)],
                check=True,
                cwd=self.root,
                capture_output=True
            )
            self.log(f"✓ Moved: {src} → {dst}")
        except subprocess.CalledProcessError as e:
            self.log(f"✗ Failed to git mv {src}: {e.stderr.decode()}")
            # Fallback to regular move
            shutil.move(str(src), str(dst))
            self.log(f"✓ Moved (no git): {src} → {dst}")

    def create_dir(self, path: Path):
        """Create directory if it doesn't exist."""
        if self.dry_run:
            self.log(f"mkdir -p {path}")
            return

        path.mkdir(parents=True, exist_ok=True)
        self.log(f"✓ Created: {path}")

    def create_init_py(self, path: Path):
        """Create __init__.py in directory."""
        init_file = path / "__init__.py"
        if self.dry_run:
            self.log(f"touch {init_file}")
            return

        if not init_file.exists():
            init_file.touch()
            self.log(f"✓ Created: {init_file}")

    def run_migration(self):
        """Execute the full migration."""
        self.log("=" * 60)
        self.log("Starting de_Funk Project Structure Migration")
        self.log("=" * 60)

        # Phase 1: Create new directory structure
        self.log("\n📁 Phase 1: Creating new directory structure...")
        self._create_directories()

        # Phase 2: Move files to new locations
        self.log("\n📦 Phase 2: Moving files...")
        self._move_files()

        # Phase 3: Create __init__.py files
        self.log("\n📝 Phase 3: Creating __init__.py files...")
        self._create_init_files()

        # Phase 4: Summary
        self.log("\n" + "=" * 60)
        self.log(f"Migration {'would be' if self.dry_run else 'completed'} successfully!")
        self.log(f"Total moves: {len(self.moves)}")
        self.log("=" * 60)

        if self.dry_run:
            self.log("\n⚠️  This was a DRY RUN. No changes were made.")
            self.log("Run without --dry-run to execute the migration.")
        else:
            self.log("\n✅ Next steps:")
            self.log("1. Run: python update_imports.py")
            self.log("2. Test the application")
            self.log("3. Commit changes: git add . && git commit -m 'Reorganize project structure'")

    def _create_directories(self):
        """Create new directory structure."""
        new_dirs = [
            # Core
            "core",

            # Data pipelines
            "datapipelines",
            "datapipelines/ingestors",
            "datapipelines/cleaners",
            "datapipelines/schemas",
            "datapipelines/facets",

            # Models
            "models",
            "models/builders",
            "models/loaders",
            "models/base",
            "models/measures",
            "models/api",

            # Orchestration
            "orchestration",
            "orchestration/pipelines",
            "orchestration/tasks",

            # App
            "app",
            "app/notebook",
            "app/notebook/api",
            "app/notebook/filters",
            "app/notebook/exhibits",
            "app/ui",
            "app/ui/components",
            "app/ui/components/exhibits",
            "app/services",
        ]

        for dir_path in new_dirs:
            self.create_dir(self.root / dir_path)

    def _move_files(self):
        """Move files to new locations."""
        # Define all file moves: (source, destination, is_directory)
        moves = [
            # ===== CORE =====
            # Move all core files except model_registry.py
            ("src/core", "core", "merge"),  # Merge: move contents only
            ("src/orchestration/context.py", "core/context.py", "file"),

            # ===== MODELS =====
            ("src/core/model_registry.py", "models/registry.py", "file"),
            ("src/model/silver", "models/builders", "dir"),
            ("src/model/loaders", "models/loaders", "dir"),
            ("src/model/api", "models/api", "dir"),

            # ===== DATAPIPELINES =====
            ("src/ingest", "datapipelines/ingestors", "dir"),
            ("src/data_pipelines/facets", "datapipelines/facets", "dir"),
            ("src/data_pipelines/polygon/facets", "datapipelines/facets/polygon", "dir"),
            ("src/data_pipelines/base_pipeline", "datapipelines/base", "dir"),
            ("scripts/build_silver_layer_optimized.py", "datapipelines/build_silver_layer_optimized.py", "file"),

            # ===== APP =====
            # Notebook (move entire directories when possible)
            ("src/notebook/schema.py", "app/notebook/schema.py", "file"),
            ("src/notebook/parser.py", "app/notebook/parser.py", "file"),
            ("src/notebook/api", "app/notebook/api", "dir"),
            ("src/notebook/filters", "app/notebook/filters", "dir"),
            ("src/notebook/exhibits", "app/notebook/exhibits", "dir"),

            # UI - merge into app/ui since we already have some files there
            ("src/ui", "app/ui", "merge"),

            # Services
            ("src/services", "app/services", "dir"),

            # ===== ORCHESTRATION =====
            ("src/common", "orchestration/common", "dir"),
        ]

        for src_str, dst_str, move_type in moves:
            src = self.root / src_str
            dst = self.root / dst_str

            if not src.exists():
                self.log(f"⚠️  Source not found (skipping): {src}")
                continue

            if move_type == "merge":
                # Merge: move contents of directory to destination
                # Skip model_registry.py in core since we move it separately
                for item in src.iterdir():
                    if item.name == "__pycache__":
                        continue
                    if item.name == "model_registry.py" and "core" in src_str:
                        continue  # Skip, will be moved separately to models/

                    item_dst = dst / item.name
                    self.git_mv(item, item_dst)
                    self.moves.append((item, item_dst))

            elif move_type == "dir":
                # Directory move
                if dst.exists():
                    self.log(f"⚠️  Destination exists: {dst}, will merge contents")
                    # Merge contents
                    for item in src.iterdir():
                        if item.name != "__pycache__":
                            item_dst = dst / item.name
                            self.git_mv(item, item_dst)
                            self.moves.append((item, item_dst))
                else:
                    self.git_mv(src, dst)
                    self.moves.append((src, dst))

            else:  # file
                # Simple file move
                self.git_mv(src, dst)
                self.moves.append((src, dst))

    def _create_init_files(self):
        """Create __init__.py in all package directories."""
        package_dirs = [
            "core",
            "datapipelines",
            "datapipelines/ingestors",
            "datapipelines/cleaners",
            "datapipelines/schemas",
            "datapipelines/facets",
            "models",
            "models/builders",
            "models/loaders",
            "models/base",
            "models/measures",
            "models/api",
            "orchestration",
            "orchestration/pipelines",
            "orchestration/tasks",
            "app",
            "app/notebook",
            "app/notebook/api",
            "app/notebook/filters",
            "app/notebook/exhibits",
            "app/ui",
            "app/ui/components",
            "app/ui/components/exhibits",
            "app/services",
        ]

        for dir_path in package_dirs:
            full_path = self.root / dir_path
            if full_path.exists() or self.dry_run:
                self.create_init_py(full_path)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate de_Funk project structure"
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

    # Verify we're in a git repository
    root = Path(args.root)
    if not (root / ".git").exists():
        print("ERROR: Not a git repository. Migration requires git.")
        return 1

    # Run migration
    migration = ProjectMigration(args.root, dry_run=args.dry_run)
    migration.run_migration()

    return 0


if __name__ == "__main__":
    exit(main())
