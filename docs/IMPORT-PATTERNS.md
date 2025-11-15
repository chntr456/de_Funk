# Import Patterns - Standardized Approach

**Status:** ✅ ACTIVE (2025-11-15)
**Branch:** `claude/standardize-config-loading-011BqXXpBbASd3reAvQ5bkcC`

---

## Executive Summary

This document defines the standardized import patterns for the de_Funk codebase. These patterns eliminate fragile path management and provide consistent, maintainable approaches for different types of files.

**Key Principle:** Different file types require different import strategies.

---

## Pattern 1: Scripts (scripts/\*.py)

**Use Case:** Executable scripts run via `python -m scripts.script_name`

**Pattern:**
```python
#!/usr/bin/env python3
"""
Script description.

Usage:
    python -m scripts.script_name --arg value
"""

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

# Now import from project modules
from models.registry import ModelRegistry
from core.context import RepoContext
```

**How to Run:**
```bash
# From repo root
python -m scripts.script_name --args

# NOT this (old way):
# python scripts/script_name.py  # ❌ Don't use
```

**Why This Works:**
- `python -m` automatically adds current directory to `sys.path`
- No bootstrap code needed
- Clean, minimal imports
- Standard Python practice

**Examples:**
- `scripts/rebuild_model.py`
- `scripts/build_all_models.py`
- `scripts/validate_migration.py`

---

## Pattern 2: Examples (examples/\*\*/\*.py)

**Use Case:** Example/demo scripts showing framework usage

**Pattern:**
```python
#!/usr/bin/env python3
"""
Example showing how to use XYZ feature.

Usage:
    python -m examples.category.example_name
"""

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

from core.context import RepoContext
# ... example code ...
```

**How to Run:**
```bash
# From repo root
python -m examples.measure_framework.01_basic_usage
```

**Why Same As Scripts:**
- Examples are also executable demonstrations
- Should be easy to run and understand
- Follow same module execution pattern

---

## Pattern 3: Entry Points (Streamlit, FastAPI, etc.)

**Use Case:** Scripts run by external tools (streamlit, uvicorn, gradio, etc.)

**Pattern:**
```python
#!/usr/bin/env python3
"""
Application description.

Usage:
    streamlit run app/ui/my_app.py
    # OR
    uvicorn app.api.main:app
"""

import sys
from pathlib import Path

# Bootstrap: External tools need explicit path setup
_current_file = Path(__file__).resolve()
_repo_root = None
for _parent in [_current_file.parent] + list(_current_file.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        _repo_root = _parent
        break
if _repo_root and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()

# Now import app modules
import streamlit as st
from app.components import MyComponent
```

**How to Run:**
```bash
streamlit run app/ui/notebook_app_duckdb.py
uvicorn app.api.main:app --reload
gradio app/ui/gradio_app.py
```

**Why Bootstrap Needed:**
- External tools (streamlit/uvicorn) run scripts in clean environment
- Repo not in `sys.path` by default
- Bootstrap finds repo root and adds to path
- Then safe to import `utils.repo`

**Examples:**
- `app/ui/notebook_app_duckdb.py` (Streamlit)
- Future: FastAPI apps, Gradio apps

---

## Pattern 4: Library Code (models/, core/, utils/, etc.)

**Use Case:** Modules imported by other code

**Pattern:**
```python
"""
Module docstring.
"""

from pathlib import Path
from typing import Optional

# NO setup_repo_imports() at module level!
# Library code is imported, not executed

class MyClass:
    def __init__(self, repo_root: Optional[Path] = None):
        """
        Initialize.

        Args:
            repo_root: Repository root. If None, auto-discovers.
        """
        if repo_root is None:
            from utils.repo import get_repo_root
            repo_root = get_repo_root()

        self.repo_root = repo_root
```

**Key Points:**
- **Never** call `setup_repo_imports()` at module level in library code
- Use lazy import of `get_repo_root()` in constructors/functions as needed
- Accept `repo_root` as optional parameter for testability
- Default to `get_repo_root()` if not provided

**Why Different:**
- Library code is imported, not executed directly
- Calling `setup_repo_imports()` at module level causes side effects
- Want clean, testable interfaces
- Let caller control path setup

**Examples:**
- `models/api/session.py`
- `core/context.py`
- `config/loader.py`

---

## Pattern 5: Tests (tests/\*\*/\*.py)

**Use Case:** Test files run by pytest or directly

**Pattern A - Unit Tests (pytest):**
```python
"""Test module docstring."""

import pytest
from pathlib import Path

# No imports needed - pytest handles sys.path


def test_something():
    from utils.repo import get_repo_root
    repo_root = get_repo_root()
    # ... test code ...
```

**Pattern B - Standalone Tests:**
```python
#!/usr/bin/env python3
"""Standalone test script."""

from pathlib import Path
import sys

# Minimal bootstrap for tests
_current = Path(__file__).resolve()
for _parent in [_current.parent] + list(_current.parents):
    if (_parent / "configs").exists() and (_parent / "core").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from utils.repo import get_repo_root
# ... test code ...

if __name__ == "__main__":
    # run tests
```

**How to Run:**
```bash
# Pytest
pytest tests/unit/test_utils_repo.py

# Standalone
python tests/unit/test_utils_repo.py
```

---

## Decision Tree

**Which pattern should I use?**

```
Is it run by an external tool (streamlit, uvicorn)?
├─ YES → Pattern 3 (Entry Point with Bootstrap)
└─ NO  → Is it executable (has `if __name__ == "__main__"`)?
          ├─ YES → Is it in scripts/ or examples/?
          │        ├─ YES → Pattern 1/2 (python -m pattern)
          │        └─ NO  → Pattern 5B (Standalone test)
          └─ NO  → Pattern 4 (Library code, no setup)
```

---

## Common Mistakes

### ❌ Mistake 1: Bootstrap in Scripts
```python
# scripts/my_script.py - WRONG!
import sys
from pathlib import Path

# Bootstrap: ...  # ❌ Not needed for scripts!
_current_file = Path(__file__).resolve()
# ...

from utils.repo import setup_repo_imports
```

**Fix:** Remove bootstrap, use `python -m scripts.my_script`

### ❌ Mistake 2: Module-Level setup_repo_imports() in Library
```python
# models/mymodel.py - WRONG!
from utils.repo import setup_repo_imports
repo_root = setup_repo_imports()  # ❌ Side effect at import!

class MyModel:
    def __init__(self):
        self.repo_root = repo_root  # ❌ Uses module-level variable
```

**Fix:** Use lazy import in `__init__`
```python
from pathlib import Path
from typing import Optional

class MyModel:
    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            from utils.repo import get_repo_root
            repo_root = get_repo_root()
        self.repo_root = repo_root
```

### ❌ Mistake 3: Running Scripts Directly
```bash
# WRONG!
python scripts/rebuild_model.py --model equity  # ❌

# CORRECT!
python -m scripts.rebuild_model --model equity  # ✅
```

### ❌ Mistake 4: Using Path.cwd()
```python
# WRONG!
repo_root = Path.cwd()  # ❌ Depends on working directory!

# CORRECT!
from utils.repo import get_repo_root
repo_root = get_repo_root()  # ✅ Works from anywhere
```

---

## Migration Checklist

When adding a new file:

- [ ] Determine file type (script/example/entry-point/library/test)
- [ ] Use appropriate pattern from above
- [ ] Update documentation to show correct usage
- [ ] Test from repo root: `python -m scripts.name` or `streamlit run app/name.py`
- [ ] Verify no import errors

When updating existing file:

- [ ] Identify current pattern (check for bootstrap/Path(__file__))
- [ ] Determine correct pattern for file type
- [ ] Replace with standardized pattern
- [ ] Update usage documentation in docstring
- [ ] Test execution: `python -m scripts.name`
- [ ] Run validation: `python scripts/validate_migration.py`

---

## Tools

**Validation:**
```bash
python scripts/validate_migration.py
```

**Check file compliance:**
```bash
# Check for old patterns
grep -r "Path(__file__).parent.parent" scripts/ examples/

# Check for bootstrap in wrong places
grep -r "# Bootstrap:" scripts/ | grep -v "add_bootstrap\|remove_bootstrap"
```

---

## Benefits

**Before (Fragile):**
- ❌ Manual `.parent.parent.parent` counting
- ❌ Breaks when moving files
- ❌ Inconsistent patterns across files
- ❌ Hardcoded paths
- ❌ Working directory dependent

**After (Robust):**
- ✅ Consistent patterns by file type
- ✅ Never breaks when reorganizing
- ✅ Standard Python practices (`python -m`)
- ✅ No hardcoded paths
- ✅ Works from any directory
- ✅ Clean, testable library code
- ✅ Well-documented usage

---

## Summary

| File Type | Pattern | How to Run | setup_repo_imports()? |
|-----------|---------|------------|----------------------|
| Scripts | `from utils.repo import setup_repo_imports; repo_root = setup_repo_imports()` | `python -m scripts.name` | ✅ Yes (module level) |
| Examples | Same as scripts | `python -m examples.name` | ✅ Yes (module level) |
| Entry Points | Bootstrap + setup_repo_imports() | `streamlit run app.py` | ✅ Yes (after bootstrap) |
| Library Code | Lazy import `get_repo_root()` in functions | Imported by others | ❌ No (only in functions) |
| Tests (pytest) | No setup needed | `pytest tests/` | ❌ No (pytest handles it) |
| Tests (standalone) | Minimal bootstrap | `python tests/test.py` | Optional |

---

**Questions?**
- See `docs/path-management-migration.md` for detailed migration guide
- See `docs/MIGRATION-COMPLETE.md` for what was accomplished
- See `utils/repo.py` for API documentation
- Run `python scripts/validate_migration.py` to check compliance
