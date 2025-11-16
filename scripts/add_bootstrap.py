#!/usr/bin/env python3
"""
Add bootstrap pattern to executable scripts.

This script adds the bootstrap pattern to scripts that need it for direct execution.
Only affects scripts that have 'from utils.repo import setup_repo_imports' but
don't already have the bootstrap.
"""

import sys
from pathlib import Path
import re

# Bootstrap for this script
_current = Path(__file__).resolve()
for _parent in [_current.parent] + list(_current.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from utils.repo import get_repo_root

BOOTSTRAP_CODE = '''import sys
from pathlib import Path

# Bootstrap: Add repo to path before importing utils.repo
_current_file = Path(__file__).resolve()
_repo_root = None
for _parent in [_current_file.parent] + list(_current_file.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        _repo_root = _parent
        break
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

'''


def needs_bootstrap(file_path: Path) -> bool:
    """Check if file needs bootstrap pattern."""
    content = file_path.read_text()

    # Must use utils.repo
    if 'from utils.repo import' not in content:
        return False

    # Must not already have bootstrap
    if '# Bootstrap:' in content or 'Bootstrap: Add repo to path' in content:
        return False

    # Should be executable (has shebang or if __name__)
    if not (content.startswith('#!') or 'if __name__ ==' in content):
        return False

    return True


def add_bootstrap_to_file(file_path: Path, dry_run: bool = True) -> bool:
    """Add bootstrap pattern to a file."""
    try:
        content = file_path.read_text()

        # Find insertion point - right after shebang and docstring
        lines = content.split('\n')
        insert_idx = 0

        # Skip shebang
        if lines[0].startswith('#!'):
            insert_idx = 1

        # Skip module docstring
        in_docstring = False
        quote_style = None
        for i in range(insert_idx, len(lines)):
            line = lines[i].strip()

            # Start of docstring
            if not in_docstring and (line.startswith('"""') or line.startswith("'''")):
                quote_style = '"""' if '"""' in line else "'''"
                in_docstring = True
                # Check if single-line docstring
                if line.count(quote_style) >= 2:
                    insert_idx = i + 1
                    break
            # End of docstring
            elif in_docstring and quote_style in line:
                insert_idx = i + 1
                break
            # Empty lines after shebang
            elif not in_docstring and not line:
                continue
            # Non-docstring content
            elif not in_docstring:
                insert_idx = i
                break

        # Skip existing imports before inserting bootstrap
        while insert_idx < len(lines) and lines[insert_idx].strip() == '':
            insert_idx += 1

        # Insert bootstrap code
        bootstrap_lines = BOOTSTRAP_CODE.rstrip().split('\n')
        for i, bootstrap_line in enumerate(bootstrap_lines):
            lines.insert(insert_idx + i, bootstrap_line)

        new_content = '\n'.join(lines)

        if not dry_run:
            # Create backup
            backup_path = file_path.with_suffix('.py.bak')
            backup_path.write_text(content)

            # Write new content
            file_path.write_text(new_content)
            print(f"✓ Added bootstrap to {file_path.name}")
        else:
            print(f"Would add bootstrap to {file_path.name}")

        return True

    except Exception as e:
        print(f"✗ Error processing {file_path.name}: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Add bootstrap pattern to executable scripts")
    parser.add_argument('--apply', action='store_true', help='Actually apply changes (default: dry run)')
    parser.add_argument('--file', type=str, help='Process specific file only')
    args = parser.parse_args()

    repo_root = get_repo_root()
    scripts_dir = repo_root / "scripts"

    if args.file:
        files_to_process = [Path(args.file)]
    else:
        # Find all Python files in scripts/
        files_to_process = list(scripts_dir.glob("*.py"))
        # Exclude this script itself
        files_to_process = [f for f in files_to_process if f.name != "add_bootstrap.py"]

    print(f"{'🔧 APPLYING' if args.apply else '🔍 DRY RUN'}: Checking {len(files_to_process)} files...")
    print()

    processed = 0
    for file_path in sorted(files_to_process):
        if needs_bootstrap(file_path):
            if add_bootstrap_to_file(file_path, dry_run=not args.apply):
                processed += 1

    print()
    print("=" * 80)
    if args.apply:
        print(f"✓ Added bootstrap to {processed} files")
        print(f"  Backups saved with .bak extension")
    else:
        print(f"🔍 DRY RUN: Would add bootstrap to {processed} files")
        print(f"  Run with --apply to actually apply changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
