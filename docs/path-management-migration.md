# Path Management Migration Guide

## Problem

The codebase has **55+ files** with duplicate, fragile path management code:

```python
# ❌ FRAGILE: Breaks when you move the file
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent  # Count parents manually!
sys.path.insert(0, str(project_root))
```

**Issues:**
- ❌ Duplicated in 55+ files
- ❌ Breaks when moving files (need to recount `.parent` levels)
- ❌ 3 different discovery implementations
- ❌ Some use `Path.cwd()` (working directory dependent)
- ❌ Inconsistent sys.path manipulation

## Solution

Use the centralized `utils/repo.py` module:

```python
# ✅ ROBUST: Works from anywhere, never breaks
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()
```

**Benefits:**
- ✅ Single line of code
- ✅ Works from any directory depth
- ✅ Never breaks when moving files
- ✅ Centralized, tested implementation
- ✅ No manual parent counting

---

## Migration Examples

### Example 1: Root-Level Scripts

**Before (11 files):**
```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Manual path discovery
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.context import RepoContext
```

**After:**
```python
#!/usr/bin/env python3
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
```

**Files affected:**
- `run_app.py`
- `run_full_pipeline.py`
- `test_forecast_view_standalone.py`
- `test_filter_system.py`
- `test_ui_state.py`
- All root-level test/debug scripts

---

### Example 2: Scripts in `scripts/` Directory

**Before (25+ files):**
```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Manual parent counting
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import RepoContext
from models.api.session import UniversalSession
```

**After:**
```python
#!/usr/bin/env python3
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
from models.api.session import UniversalSession
```

**Files affected:**
- `scripts/build_equity_silver.py`
- `scripts/build_all_models.py`
- `scripts/run_forecasts.py`
- `scripts/test_pipeline_e2e.py`
- All 25+ scripts in `scripts/` directory

---

### Example 3: Deeply Nested Files (examples/, tests/)

**Before (11 files):**
```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Three levels of parent navigation!
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

from core.context import RepoContext
```

**After:**
```python
#!/usr/bin/env python3
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
```

**Files affected:**
- `examples/measure_framework/01_basic_usage.py`
- `examples/providers/custom_provider_example.py`
- `tests/unit/test_backend_adapters.py`
- `app/ui/notebook_app_duckdb.py`
- All deeply nested scripts

---

### Example 4: Scripts Using Path.cwd() (Dangerous!)

**Before (12 files):**
```python
from pathlib import Path

# ❌ WRONG: Only works if run from repo root!
repo_root = Path.cwd()

# Or worse:
def __init__(self, repo_root: Path = None):
    self.repo_root = repo_root or Path.cwd()  # Dangerous default!
```

**After:**
```python
from utils.repo import get_repo_root

# ✅ CORRECT: Works from anywhere
repo_root = get_repo_root()

# Or for class defaults:
def __init__(self, repo_root: Path = None):
    from utils.repo import get_repo_root
    self.repo_root = repo_root or get_repo_root()
```

**Files affected:**
- `models/api/session.py:61`
- `app/notebook/managers/notebook_manager.py:59`
- `orchestration/common/path_utils.py:8`
- Any file using `Path.cwd()` for repo root

---

### Example 5: Hardcoded Absolute Paths

**Before (1 file - worst case!):**
```python
import sys

# ❌ WORST: Hardcoded path!
sys.path.insert(0, '/home/user/de_Funk')

from core.context import RepoContext
```

**After:**
```python
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
```

**Files affected:**
- `debug_exchange_data.py:25`

---

## Special Case: Entry-Point Scripts

For scripts run directly by external tools (e.g., `streamlit run app.py`, `uvicorn app:main`), you need a **bootstrap** before importing `utils.repo`:

```python
import sys
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

# Now safe to import
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()
```

**Why needed?** External tools run scripts in a clean Python environment where the repo isn't in `sys.path` yet. The bootstrap finds and adds the repo before importing `utils.repo`.

**Examples of entry-point scripts:**
- Streamlit apps: `streamlit run app/ui/notebook_app_duckdb.py`
- FastAPI/Uvicorn: `uvicorn app.main:app`
- Gradio apps: `gradio app/ui/gradio_app.py`

**Not needed for:**
- Scripts run via `python scripts/my_script.py` (normal scripts)
- Modules imported by other code
- Library code

---

## API Reference

### `setup_repo_imports()` - Recommended for Scripts

```python
from utils.repo import setup_repo_imports

# One-liner to set up everything
repo_root = setup_repo_imports()

# Now import from anywhere in the repo
from core.context import RepoContext
from models.api.session import UniversalSession
```

**Use when:**
- Writing scripts that need to import from the repo
- You want automatic sys.path setup
- Most common use case (95% of scripts)

---

### `get_repo_root()` - Just Get the Path

```python
from utils.repo import get_repo_root

# Just get the repo root, don't modify sys.path
repo_root = get_repo_root()

# Use for file path construction
config_path = repo_root / "configs" / "storage.json"
```

**Use when:**
- You need the repo root path but don't need imports
- You're already using ConfigLoader or RepoContext
- Building file paths

---

### `repo_imports()` - Context Manager (Advanced)

```python
from utils.repo import repo_imports

# Temporarily add to sys.path, auto-cleanup
with repo_imports() as repo_root:
    from core.context import RepoContext
    ctx = RepoContext.from_repo_root()
    # ... your code ...
# sys.path restored after exiting
```

**Use when:**
- You want automatic cleanup
- Writing library code that shouldn't pollute sys.path
- Testing scenarios

---

### `verify_repo_structure()` - Validation

```python
from utils.repo import verify_repo_structure

# Check if repo structure is valid
if not verify_repo_structure():
    print("ERROR: Invalid repository structure!")
    exit(1)
```

**Use when:**
- Debugging setup issues
- Validating environment in CI/CD
- Pre-flight checks in scripts

---

## Migration Strategy

### Phase 1: Update New Scripts (Immediate)

All new scripts should use `setup_repo_imports()`:

```python
#!/usr/bin/env python3
"""My new script."""
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

# Your code here...
```

### Phase 2: Update Active Scripts (Next Sprint)

Priority order:
1. **Scripts with hardcoded paths** (1 file) - HIGH PRIORITY
2. **Scripts using Path.cwd()** (12 files) - HIGH PRIORITY
3. **Root-level scripts** (11 files) - MEDIUM
4. **Scripts/ directory** (25 files) - MEDIUM
5. **Examples/ and tests/** (18 files) - LOW

### Phase 3: Update Libraries (Gradual)

Update class defaults that use `Path.cwd()`:

```python
# Before
class UniversalSession:
    def __init__(self, repo_root: Path = None):
        self.repo_root = repo_root or Path.cwd()

# After
class UniversalSession:
    def __init__(self, repo_root: Path = None):
        if repo_root is None:
            from utils.repo import get_repo_root
            repo_root = get_repo_root()
        self.repo_root = repo_root
```

### Phase 4: Deprecate Old Functions (Future)

Mark old discovery functions as deprecated:
- `orchestration/common/path_utils.py::repo_root()`
- `utils/env_loader.py::find_dotenv()` (partially - still used for .env)

---

## Automated Migration Script

Want to migrate files automatically? Use this script:

```python
#!/usr/bin/env python3
"""
Automatically migrate scripts to use utils.repo.

Usage:
    python migrate_to_utils_repo.py <script_path>
"""

import re
import sys
from pathlib import Path

def migrate_script(script_path: Path) -> bool:
    """Migrate a single script to use utils.repo."""
    content = script_path.read_text()

    # Pattern 1: sys.path.insert with Path(__file__).parent...
    pattern1 = r'(?:project_root|repo_root|REPO_ROOT)\s*=\s*Path\(__file__\)\.(?:parent\.?)+.*?\n.*?sys\.path\.(?:insert|append)\(.*?\)'

    # Pattern 2: Just sys.path.insert
    pattern2 = r'sys\.path\.(?:insert|append)\(\d+,\s*str\(Path\(__file__\)\.(?:parent\.?)+.*?\)\)'

    # Check if already migrated
    if 'from utils.repo import' in content:
        print(f"✓ {script_path.name} already migrated")
        return False

    # Check if needs migration
    if not (re.search(pattern1, content, re.DOTALL) or re.search(pattern2, content)):
        print(f"⊘ {script_path.name} doesn't need migration")
        return False

    # Backup original
    backup_path = script_path.with_suffix('.py.bak')
    backup_path.write_text(content)

    # Replace patterns
    new_content = re.sub(pattern1, '', content, flags=re.DOTALL)
    new_content = re.sub(pattern2, '', new_content)

    # Add import after shebang/docstring
    lines = new_content.split('\n')
    insert_idx = 0

    # Skip shebang
    if lines[0].startswith('#!'):
        insert_idx = 1

    # Skip docstring
    in_docstring = False
    for i, line in enumerate(lines[insert_idx:], start=insert_idx):
        if '"""' in line or "'''" in line:
            in_docstring = not in_docstring
            if not in_docstring:
                insert_idx = i + 1
                break

    # Insert import
    lines.insert(insert_idx, 'from utils.repo import setup_repo_imports')
    lines.insert(insert_idx + 1, 'repo_root = setup_repo_imports()')
    lines.insert(insert_idx + 2, '')

    # Clean up extra blank lines
    new_content = '\n'.join(lines)
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    # Write migrated version
    script_path.write_text(new_content)
    print(f"✓ {script_path.name} migrated (backup: {backup_path.name})")
    return True

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python migrate_to_utils_repo.py <script_path>")
        sys.exit(1)

    script_path = Path(sys.argv[1])
    if not script_path.exists():
        print(f"ERROR: {script_path} not found")
        sys.exit(1)

    migrate_script(script_path)
```

---

## Comparison: Before vs After

### Before (Fragile, Duplicated)

| File Location | Lines of Code | Parents |
|---------------|---------------|---------|
| `run_app.py` | 3-4 lines | `.parent` |
| `scripts/build_equity_silver.py` | 3-4 lines | `.parent.parent` |
| `examples/measure_framework/01_basic_usage.py` | 4-5 lines | `.parent.parent.parent` |

**Total duplication:** ~165-220 lines across 55 files

### After (Robust, Centralized)

| File Location | Lines of Code | Function Call |
|---------------|---------------|---------------|
| Any file | 2 lines | `setup_repo_imports()` |

**Total duplication:** ~110 lines across 55 files (47% reduction)

---

## Testing

After migration, verify each script still works:

```bash
# Test from repo root
python scripts/build_equity_silver.py

# Test from different directory (should still work!)
cd /tmp
python /path/to/de_Funk/scripts/build_equity_silver.py

# Test deeply nested
python examples/measure_framework/01_basic_usage.py
```

---

## Troubleshooting

### Import Error: No module named 'utils.repo'

**Problem:** The `utils/repo.py` file doesn't exist yet.

**Solution:** Ensure you've pulled the latest code with the new `utils/repo.py` module.

### Still getting ModuleNotFoundError

**Problem:** The import is happening before `setup_repo_imports()`.

**Solution:** Move `setup_repo_imports()` to the very top of your script:

```python
# ✅ CORRECT
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext  # Now works!

# ❌ WRONG
from core.context import RepoContext  # Fails!

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()
```

### Circular Import

**Problem:** `utils/repo.py` is imported by `config/loader.py`, which is imported by other modules.

**Solution:** Use lazy import or conditional import:

```python
# In utils/repo.py
def get_repo_root():
    # ... implementation ...
    pass

# Don't import from config at module level!
```

---

## Summary

**Migration Steps:**
1. ✅ Replace manual path discovery with `setup_repo_imports()`
2. ✅ Remove manual `sys.path.insert()` calls
3. ✅ Remove manual `.parent.parent.parent` counting
4. ✅ Test from different working directories
5. ✅ Clean up backup files once verified

**Impact:**
- **55+ files** simplified
- **~110 lines** of duplicated code removed
- **Zero** manual parent counting
- **100%** robust to file moves

**Next Steps:**
1. Start with high-priority files (hardcoded paths, Path.cwd())
2. Gradually migrate active scripts
3. Update examples and tests
4. Deprecate old discovery functions
