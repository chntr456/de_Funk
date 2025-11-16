#!/usr/bin/env python3
"""
Remove bootstrap pattern from scripts and update to python -m pattern.

This script:
1. Removes bootstrap code from scripts
2. Keeps simple utils.repo imports
3. Updates documentation to show python -m usage
"""

import sys
import re
from pathlib import Path

# Bootstrap for this script (will be removed after migration)
_current = Path(__file__).resolve()
for _parent in [_current.parent] + list(_current.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from utils.repo import get_repo_root

# Bootstrap pattern to remove (match with or without trailing newline)
BOOTSTRAP_PATTERN = re.compile(
    r'# Bootstrap:.*?\n'
    r'_current_file = Path\(__file__\)\.resolve\(\)\n'
    r'_repo_root = None\n'
    r'for _parent in \[_current_file\.parent\] \+ list\(_current_file\.parents\):\n'
    r'    if \(_parent / "configs"\)\.exists\(\) and \(_parent / "core"\)\.exists\(\):\n'
    r'        _repo_root = _parent\n'
    r'        break\n'
    r'if _repo_root and str\(_repo_root\) not in sys\.path:\n'
    r'    sys\.path\.insert\(0, str\(_repo_root\)\)\n',
    re.MULTILINE
)


def remove_bootstrap(file_path: Path, dry_run: bool = True) -> bool:
    """Remove bootstrap pattern from file."""
    try:
        content = file_path.read_text()

        # Check if has bootstrap
        if '# Bootstrap:' not in content:
            return False

        # Remove bootstrap pattern
        new_content = BOOTSTRAP_PATTERN.sub('', content)

        # Clean up duplicate imports that may remain
        new_content = clean_duplicate_imports(new_content)

        # Update usage documentation if present
        new_content = update_usage_docs(file_path.stem, new_content)

        if content == new_content:
            return False

        if not dry_run:
            # Backup
            backup_path = file_path.with_suffix('.py.bak2')
            backup_path.write_text(content)

            # Write
            file_path.write_text(new_content)
            print(f"✓ Removed bootstrap from {file_path.name}")
        else:
            print(f"Would remove bootstrap from {file_path.name}")

        return True

    except Exception as e:
        print(f"✗ Error processing {file_path.name}: {e}")
        return False


def clean_duplicate_imports(content: str) -> str:
    """Remove duplicate import statements."""
    lines = content.split('\n')
    seen_imports = set()
    new_lines = []

    for line in lines:
        # Check if it's an import line
        if line.strip().startswith(('import ', 'from ')):
            if line in seen_imports:
                # Skip duplicate
                continue
            seen_imports.add(line)

        new_lines.append(line)

    return '\n'.join(new_lines)


def update_usage_docs(script_name: str, content: str) -> str:
    """Update usage documentation to show python -m pattern."""

    # Pattern 1: python scripts/script_name.py → python -m scripts.script_name
    content = re.sub(
        r'python scripts/' + script_name + r'\.py',
        f'python -m scripts.{script_name}',
        content
    )

    # Pattern 2: ./scripts/script_name.py → python -m scripts.script_name
    content = re.sub(
        r'\./scripts/' + script_name + r'\.py',
        f'python -m scripts.{script_name}',
        content
    )

    return content


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Remove bootstrap from scripts")
    parser.add_argument('--apply', action='store_true', help='Actually apply changes')
    args = parser.parse_args()

    repo_root = get_repo_root()
    scripts_dir = repo_root / "scripts"

    # Find all Python files in scripts/
    files_to_process = list(scripts_dir.glob("*.py"))
    files_to_process = [f for f in files_to_process if f.name not in ["remove_bootstrap.py", "add_bootstrap.py"]]

    print(f"{'🔧 APPLYING' if args.apply else '🔍 DRY RUN'}: Checking {len(files_to_process)} files...")
    print()

    processed = 0
    for file_path in sorted(files_to_process):
        if remove_bootstrap(file_path, dry_run=not args.apply):
            processed += 1

    print()
    print("=" * 80)
    if args.apply:
        print(f"✓ Removed bootstrap from {processed} files")
        print(f"  Scripts now use python -m scripts.script_name pattern")
        print(f"  Backups saved with .bak2 extension")
    else:
        print(f"🔍 DRY RUN: Would remove bootstrap from {processed} files")
        print(f"  Run with --apply to actually apply changes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
