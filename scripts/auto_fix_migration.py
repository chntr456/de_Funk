#!/usr/bin/env python3
"""
Auto-fix migration issues in Python files.

This script automatically fixes common migration issues:
1. Replace old path patterns with utils.repo
2. Fix API mismatches (get_model().model_cfg → get_model_config())
3. Remove sys.path manipulation
4. Standardize imports

Usage:
    python -m scripts.auto_fix_migration  # Dry run (shows what would change)
    python -m scripts.auto_fix_migration --apply  # Actually apply fixes
    python -m scripts.auto_fix_migration --file path/to/file.py  # Fix single file
"""

import sys
from pathlib import Path

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

# Bootstrap
_current = Path(__file__).resolve()
for _parent in [_current.parent] + list(_current.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from utils.repo import get_repo_root

@dataclass
class Fix:
    """Represents a fix applied to a file."""
    file: Path
    line_num: int
    old_code: str
    new_code: str
    description: str

class MigrationFixer:
    """Automatically fix migration issues."""

    def __init__(self, repo_root: Path, dry_run: bool = True):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.fixes_applied: List[Fix] = []

    def fix_file(self, file_path: Path) -> List[Fix]:
        """Fix a single file and return list of fixes applied."""
        try:
            content = file_path.read_text()
            original_content = content
            fixes = []

            # Apply fixes in order
            content, file_fixes = self._fix_path_patterns(file_path, content)
            fixes.extend(file_fixes)

            content, file_fixes = self._fix_api_mismatches(file_path, content)
            fixes.extend(file_fixes)

            # Only write if changes were made
            if content != original_content:
                if not self.dry_run:
                    # Create backup
                    backup_path = file_path.with_suffix('.py.bak')
                    backup_path.write_text(original_content)

                    # Write fixed content
                    file_path.write_text(content)

                self.fixes_applied.extend(fixes)

            return fixes

        except Exception as e:
            print(f"❌ Error fixing {file_path}: {e}")
            return []

    def _fix_path_patterns(self, file_path: Path, content: str) -> Tuple[str, List[Fix]]:
        """Fix old path management patterns."""
        fixes = []
        lines = content.split('\n')
        new_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Pattern 1: sys.path.insert/append with Path(__file__)
            if re.search(r"sys\.path\.(insert|append)\(.*?Path\(__file__\)", line):
                # Look backward for associated imports
                start_idx = i
                while start_idx > 0 and (
                    'import sys' in lines[start_idx - 1] or
                    'from pathlib import Path' in lines[start_idx - 1] or
                    lines[start_idx - 1].strip().startswith('#')
                ):
                    start_idx -= 1

                # Found the block to replace
                old_block = '\n'.join(lines[start_idx:i+1])

                # Create replacement
                replacement = [
                    "from utils.repo import setup_repo_imports",
                    "repo_root = setup_repo_imports()",
                ]

                fixes.append(Fix(
                    file=file_path,
                    line_num=start_idx + 1,
                    old_code=old_block,
                    new_code='\n'.join(replacement),
                    description="Replaced sys.path manipulation with setup_repo_imports()"
                ))

                # Add replacement lines
                new_lines.extend(replacement)

                # Skip the old lines
                i += 1
                continue

            # Pattern 2: Standalone Path(__file__) with .parent chains (not in sys.path)
            path_parent_match = re.search(r'(\w+)\s*=\s*Path\(__file__\)\.parent(\.parent)*', line)
            if path_parent_match and 'sys.path' not in line:
                var_name = path_parent_match.group(1)

                # Replace with get_repo_root()
                new_line = line.replace(
                    path_parent_match.group(0),
                    f"{var_name} = get_repo_root()"
                )

                # Check if we need to add import
                needs_import = 'from utils.repo import get_repo_root' not in content

                fixes.append(Fix(
                    file=file_path,
                    line_num=i + 1,
                    old_code=line,
                    new_code=new_line + (" # (needs: from utils.repo import get_repo_root)" if needs_import else ""),
                    description=f"Replaced Path(__file__).parent with get_repo_root()"
                ))

                new_lines.append(new_line)
                i += 1
                continue

            new_lines.append(line)
            i += 1

        return '\n'.join(new_lines), fixes

    def _fix_api_mismatches(self, file_path: Path, content: str) -> Tuple[str, List[Fix]]:
        """Fix API mismatches."""
        fixes = []

        # Pattern: registry.get_model_config(name)
        def replace_get_model(match):
            model_name = match.group(1)
            fixes.append(Fix(
                file=file_path,
                line_num=0,  # Will update with actual line number
                old_code=match.group(0),
                new_code=f"registry.get_model_config({model_name})",
                description="Fixed get_model().model_cfg → get_model_config()"
            ))
            return f"registry.get_model_config({model_name})"

        content = re.sub(
            r"registry\.get_model\(([^)]+)\)\.model_cfg",
            replace_get_model,
            content
        )

        # Pattern: Path.cwd() defaults
        content = re.sub(
            r"repo_root\s*=\s*repo_root\s+or\s+Path\.cwd\(\)",
            "repo_root = repo_root or get_repo_root()",
            content
        )

        return content, fixes

    def fix_all(self, target_files: Optional[List[Path]] = None) -> int:
        """Fix all files or specific target files."""
        if target_files is None:
            # Get files from validation
            target_files = []
            from validate_migration import MigrationValidator

            validator = MigrationValidator(self.repo_root)
            python_files = validator.find_python_files()

            for file_path in python_files:
                result = validator.validate_file(file_path)
                if not result.passed:
                    target_files.append(file_path)

        print(f"{'🔍 DRY RUN: ' if self.dry_run else '🔧 FIXING: '}{len(target_files)} files...")
        print()

        total_fixes = 0
        for file_path in target_files:
            fixes = self.fix_file(file_path)

            if fixes:
                rel_path = file_path.relative_to(self.repo_root)
                print(f"{'Would fix' if self.dry_run else 'Fixed'}: {rel_path}")

                for fix in fixes:
                    print(f"  ✓ {fix.description}")

                total_fixes += len(fixes)
                print()

        return total_fixes

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Auto-fix migration issues")
    parser.add_argument('--apply', action='store_true', help='Actually apply fixes (default: dry run)')
    parser.add_argument('--file', type=str, help='Fix specific file only')
    args = parser.parse_args()

    repo_root = get_repo_root()
    fixer = MigrationFixer(repo_root, dry_run=not args.apply)

    if args.file:
        target_files = [Path(args.file)]
    else:
        target_files = None

    total_fixes = fixer.fix_all(target_files)

    print("=" * 80)
    if args.apply:
        print(f"✅ Applied {total_fixes} fixes")
        print("Backups created with .bak extension")
    else:
        print(f"🔍 DRY RUN: Would apply {total_fixes} fixes")
        print("Run with --apply to actually apply fixes")

    return 0 if total_fixes >= 0 else 1

if __name__ == "__main__":
    sys.exit(main())
