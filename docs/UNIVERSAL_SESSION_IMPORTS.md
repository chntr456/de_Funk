# Universal Session - Import Chain & Dependency Analysis

## File Location
`/home/user/de_Funk/models/api/session.py` (1122 lines)

## Import Chain Overview

### Core Module Imports (Top of File)

```python
from __future__ import annotations                      # PEP 563: Postponed evaluation
import json                                              # JSON parsing
from pathlib import Path                                 # Path handling
from typing import Dict, Any, List, Optional, Tuple, Set, TYPE_CHECKING  # Type hints

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame  # Type hints only (no runtime)
else:
    SparkDataFrame = Any                                 # Fallback for DuckDB-only

# Core application imports
try:
    from models.api.dal import StorageRouter, BronzeTable  # Path resolution
except ImportError:
    # Fallback if pyspark not available (DuckDB-only mode)
    @dataclass(frozen=True)
    class StorageRouter:
        storage_cfg: Dict[Any, Any]
        def bronze_path(self, logical_table: str) -> str: ...
        def silver_path(self, logical_rel: str) -> str: ...
    BronzeTable = None

from core.session.filters import FilterEngine             # Filter application

try:
    import yaml  # type: ignore
except Exception:
    yaml = None
```

### Dynamic Imports (Lazy - Inside Methods)

```python
# Inside __init__() - Line 93
from models.registry import ModelRegistry

# Inside __init__() - Line 101
from models.api.graph import ModelGraph

# Inside load_model() - Line 212
from models.base.model import BaseModel
```

---

## Dependency Tree

### Level 1: UniversalSession Core

```
UniversalSession
├─ Initializations (in __init__)
│  ├─ self.connection        # Spark/DuckDB connection
│  ├─ self.storage_cfg       # Dict config
│  ├─ self.repo_root         # Path
│  ├─ self._models = {}      # Model cache
│  ├─ ModelRegistry()        # ← Dynamic import
│  ├─ ModelGraph()           # ← Dynamic import
│  └─ Optional model pre-load
└─ Methods
   ├─ load_model() →        # Uses dynamic BaseModel import
   ├─ get_table() →         # Uses FilterEngine + model methods
   ├─ _execute_auto_joins() → # Backend-specific logic
   └─ _aggregate_data() →   # Backend-specific aggregation
```

### Level 2: Dependencies

```
UniversalSession
├── StorageRouter (models/api/dal.py)
│   ├─ Dataclass: frozen=True
│   ├─ Methods:
│   │  ├─ bronze_path(logical_table) → str
│   │  └─ silver_path(logical_rel) → str
│   └─ Dependencies: None (just dataclass, Path, Dict)
│
├── FilterEngine (core/session/filters.py)
│   ├─ Static methods only
│   ├─ Methods:
│   │  ├─ apply_filters(df, filters, backend)
│   │  ├─ apply_from_session(df, filters, session)
│   │  ├─ _apply_spark_filters(df, filters)
│   │  ├─ _apply_duckdb_filters(df, filters)
│   │  └─ build_filter_sql(filters) → str
│   ├─ Dependencies:
│   │  ├─ pandas (pd.DataFrame)
│   │  ├─ pyspark.sql.functions (F) - optional
│   │  └─ (No UniversalSession dependency!)
│
├── ModelRegistry (models/registry.py)
│   ├─ Discovers models from configs/models/
│   ├─ Methods:
│   │  ├─ get_model_config(model_name) → Dict
│   │  ├─ get_model_class(model_name) → type
│   │  ├─ register_model_class(model_name, class)
│   │  └─ _try_auto_register(model_name)
│   ├─ Uses:
│   │  ├─ ModelConfig dataclass
│   │  ├─ YAML loading
│   │  └─ Lazy imports for model classes
│   └─ Dependencies:
│       ├─ pathlib (Path)
│       ├─ yaml (safe_load)
│       ├─ typing
│       └─ No circular deps (uses lazy imports)
│
├── ModelGraph (models/api/graph.py)
│   ├─ Uses NetworkX for DAG management
│   ├─ Methods:
│   │  ├─ build_from_config_dir(config_dir)
│   │  ├─ are_related(model_a, model_b) → bool
│   │  ├─ get_dependencies(model_name) → Set[str]
│   │  ├─ get_join_path(model_a, model_b) → List[str]
│   │  └─ get_build_order() → List[str]
│   └─ Dependencies:
│       ├─ networkx (nx.DiGraph)
│       ├─ pathlib, yaml, typing
│       └─ No circular deps
│
└── BaseModel (models/base/model.py) [Lazy loaded]
    ├─ Base class for all models
    ├─ Methods:
    │  ├─ get_table(table_name)
    │  ├─ get_table_schema(table_name)
    │  └─ set_session(session)
    ├─ Uses:
    │  ├─ StorageRouter (same module as UniversalSession uses)
    │  ├─ DuckDBAdapter or SparkAdapter
    │  └─ self.session (injected by UniversalSession)
    └─ Dependencies:
        ├─ pyspark.sql (optional, with graceful fallback)
        ├─ storage router
        └─ Connection (Spark/DuckDB)
```

### Level 3: Deep Dependencies

```
StorageRouter
└─ Path, Dict, Optional
   └─ Standard library only

FilterEngine
├─ pandas.DataFrame
├─ pyspark.sql.functions (F)
└─ typing

ModelRegistry
├─ pathlib.Path
├─ yaml
├─ typing
├─ dataclasses (ModelConfig, TableConfig, MeasureConfig)
└─ Lazy imports for:
   ├─ models.implemented.company.model.CompanyModel
   ├─ models.implemented.stocks.model.StocksModel
   └─ etc.

ModelGraph
├─ networkx (as nx)
├─ pathlib, yaml, typing
└─ Sets/graph algorithms

BaseModel
├─ pyspark.sql (optional fallback)
├─ pathlib, typing
├─ StorageRouter (dal.py)
├─ Backend adapters
├─ Connection (Spark/DuckDB)
└─ Optional: Python measures module
```

---

## Circular Dependency Prevention

### Strategy 1: TYPE_CHECKING Guard

**Purpose:** Import types for type hints without runtime overhead

```python
# Top of models/api/session.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame
else:
    SparkDataFrame = Any

# Why this works:
# - TYPE_CHECKING is False at runtime
# - PySpark not imported at module load (allows DuckDB-only)
# - Type checkers (mypy, pyright) see the real import
# - No circular import because PySpark import is skipped
```

### Strategy 2: Lazy Imports Inside Methods

**Purpose:** Load dependencies only when actually used

```python
# Inside __init__ method (line 93)
def __init__(self, ...):
    # Only import ModelRegistry when UniversalSession is created
    from models.registry import ModelRegistry
    models_dir = repo_root / "configs" / "models"
    self.registry = ModelRegistry(models_dir)
    
    # Why this works:
    # - ModelRegistry not imported when module loads
    # - Only imported when UniversalSession() called
    # - Breaks potential circular dependency chains
```

```python
# Inside load_model method (line 212)
def load_model(self, model_name: str):
    if model_name in self._models:
        return self._models[model_name]
    
    # Import BaseModel only when loading a model
    from models.base.model import BaseModel
    
    try:
        model_class = self.registry.get_model_class(model_name)
    except ValueError:
        model_class = BaseModel
    
    # Why this works:
    # - BaseModel not imported until first model load
    # - Multiple imports are cached by Python
    # - Safe from circular dependencies
```

### Strategy 3: Try/Except Import

**Purpose:** Graceful fallback for optional dependencies

```python
# For PySpark (optional, used by Spark backend)
try:
    from models.api.dal import StorageRouter, BronzeTable
except ImportError:
    # Fallback for DuckDB-only environments
    @dataclass(frozen=True)
    class StorageRouter:
        storage_cfg: Dict[Any, Any]
        repo_root: Optional[Path] = None
        
        def bronze_path(self, logical_table: str) -> str:
            # Simplified implementation
            ...

# Why this works:
# - If pyspark not available, define minimal StorageRouter
# - DuckDB-only environments work fine
# - No hard dependency on PySpark
```

---

## Import Order & Timing

### Module Load Phase (when module is first imported)

```
1. from __future__ import annotations   ✓ (immediate)
2. import json, pathlib, typing         ✓ (immediate)
3. if TYPE_CHECKING: ...                ✓ (immediate, skipped at runtime)
4. try: from models.api.dal ...         ✓ (immediate)
5. from core.session.filters ...        ✓ (immediate)
6. try: import yaml                     ✓ (immediate)
7. class UniversalSession:              ✓ (immediate)
8. No other imports executed            ← LAZY LOADING!
```

### Instance Creation Phase (when UniversalSession(...) called)

```
1. __init__ starts
2. [Line 93] from models.registry import ModelRegistry      ← 1st lazy import
3. [Line 101] from models.api.graph import ModelGraph       ← 2nd lazy import
4. Optionally pre-load models (if specified)
```

### Model Loading Phase (when load_model() called)

```
1. [Line 212] from models.base.model import BaseModel       ← 3rd lazy import
2. Get model config from registry
3. Get model class (or use BaseModel)
4. Instantiate model with connection, configs, etc.
```

### Aggregation Phase (when _aggregate_data() called)

```
1. [Line 1031] from pyspark.sql import functions as F      ← 4th lazy import
   (Only if Spark backend and aggregation needed)
2. Build aggregation expressions
3. Apply to DataFrame
```

---

## Dependency Isolation

### No Circular Dependencies

```
✓ UniversalSession → ModelRegistry (one-way)
✓ UniversalSession → ModelGraph (one-way)
✓ UniversalSession → FilterEngine (one-way)
✓ UniversalSession → BaseModel (lazy, one-way)
✓ ModelRegistry ↔ Models (lazy auto-registration)
✓ ModelGraph (isolated, uses only networkx)
✓ FilterEngine (isolated, no UniversalSession reference)
```

### Clean Separation of Concerns

```
UniversalSession (orchestration)
├─ Delegates model discovery → ModelRegistry
├─ Delegates relationship queries → ModelGraph
├─ Delegates filter logic → FilterEngine
├─ Delegates model instantiation → BaseModel
└─ Never imports downstream modules
   (Downstream modules can optionally reference session for cross-model access)
```

---

## Module Graph Visualization

```
┌─────────────────────────────────────────────────────────────┐
│  Python typing module                                       │
│  - TYPE_CHECKING (False at runtime)                         │
│  - Dict, Any, List, Optional, Tuple, Set                   │
└─────────────────────────────────────────────────────────────┘
                    ↑
                    │
                    │ (conditional import)
                    │
┌─────────────────────────────────────────────────────────────┐
│  UniversalSession (models/api/session.py)                   │
│  ┌─────────────┬──────────────┬─────────────────────┐      │
│  │ MODULE LOAD │ INSTANCE     │ METHOD CALL        │      │
│  │ PHASE       │ CREATION     │ (lazy imports)     │      │
│  │             │              │                    │      │
│  │ import PATH │ from models. │ from models.base.  │      │
│  │ import TYPE │ registry ... │ model import ...   │      │
│  │             │ from models. │                    │      │
│  │ import JSON │ api.graph..  │ from pyspark.sql.  │      │
│  │             │              │ functions import F │      │
│  └─────────────┴──────────────┴─────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
        ↑                   ↑                   ↑
        │                   │                   │
   (early)            (when created)      (when called)
        │                   │                   │
        │                   └───────┬───────────┘
        │                           │
        ├─→ FilterEngine ──────────→ (isolated static methods)
        │   (core/session/filters.py)
        │
        ├─→ StorageRouter ─────────→ (dataclass, no dependencies)
        │   (models/api/dal.py)
        │
        └─→ ModelRegistry ─────────→ (at __init__)
            ModelGraph          (at __init__)
            BaseModel           (at load_model)
            (lazy loading)
```

---

## Import Statistics

### Total Imports in session.py

- **Module-level imports**: 7 (from __future__, import, from typing)
- **TYPE_CHECKING imports**: 1 (pyspark - type hints only)
- **Try/except imports**: 1 (models.api.dal with fallback)
- **Early imports**: 1 (FilterEngine)
- **Lazy imports**: 4+ (in methods)
- **Total direct dependencies**: 5-6 main modules

### Memory Footprint at Module Load

```
Before any UniversalSession creation:
- Core imports: typing, pathlib, json, yaml (standard lib + yaml)
- FilterEngine class definition
- StorageRouter dataclass definition (or import)
- UniversalSession class definition
≈ ~1-2 MB (excluding PySpark/DuckDB)

After UniversalSession(...) creation:
+ ModelRegistry loaded
+ ModelGraph loaded
+ YAML configs parsed
≈ ~5-10 MB (depending on number of models)

After first model load:
+ BaseModel loaded
+ Backend adapter loaded
+ Actual data loading starts
≈ ~50+ MB (depending on data size)
```

### Optional Dependencies

```
Optional (with graceful fallbacks):
- pyspark.sql (TYPE_CHECKING import, only used if Spark backend)
- pyspark.sql.functions (lazy import in _aggregate_spark)
- networkx (required by ModelGraph)
- yaml (try/except, used for config parsing)

Required:
- Standard library: pathlib, json, typing, dataclasses
- pandas (via DuckDB and FilterEngine)
```

---

## Circular Dependency Prevention Checklist

When adding new imports:

- [ ] Is it a core dependency needed at module load? Keep at top
- [ ] Is it only used in specific methods? Move to method (lazy import)
- [ ] Could it cause circular import? Use TYPE_CHECKING or lazy load
- [ ] Is it optional (Spark, PySpark)? Use try/except
- [ ] Does downstream code reference UniversalSession? Pass as parameter, don't import

### Safe Import Patterns

✓ **Safe: Top-level, no cycles**
```python
from core.session.filters import FilterEngine  # No cycle possible
```

✓ **Safe: TYPE_CHECKING conditional**
```python
if TYPE_CHECKING:
    from pyspark.sql import DataFrame  # Not imported at runtime
```

✓ **Safe: Lazy import in method**
```python
def method(self):
    from models.registry import ModelRegistry  # Only on first call
```

✓ **Safe: Try/except fallback**
```python
try:
    from pyspark.sql import ...
except ImportError:
    # Fallback implementation
```

✗ **Unsafe: Circular import at top-level**
```python
from models.base.model import BaseModel  # model.py might import session
```

✗ **Unsafe: Hidden circular via TYPE_CHECKING**
```python
if TYPE_CHECKING:
    from models.base.model import BaseModel  # if model imports UniversalSession
```

---

## Testing Import Chain

### Verify No Circular Dependencies

```bash
# Using Python's import system
python -c "from models.api.session import UniversalSession; print('✓ Import successful')"

# With import tracing (verbose)
python -c "import sys; sys.settrace(lambda *args: None); from models.api.session import UniversalSession" 2>&1 | grep -i circular
```

### Check Lazy Load Behavior

```python
import sys

# Before import
print(f"Modules before: {len(sys.modules)}")

# Import UniversalSession (should be minimal)
from models.api.session import UniversalSession
print(f"After import: {len(sys.modules)}")  # Only +7-10 modules

# Create instance (triggers ModelRegistry, ModelGraph)
session = UniversalSession(...)
print(f"After create: {len(sys.modules)}")  # +10-20 modules

# Load model (triggers BaseModel)
session.load_model('stocks')
print(f"After load_model: {len(sys.modules)}")  # +20-30 modules
```

---

## Best Practices

### For Contributors

1. **Keep UniversalSession methods focused**
   - One logical operation per method
   - Lazy load dependencies if used in specific methods only

2. **Use TYPE_CHECKING for type hints**
   - Avoid importing backends at module level
   - Add `# type: ignore` for optional imports

3. **Never import UniversalSession in dependencies**
   - ModelRegistry, FilterEngine, etc. should be independent
   - If they need UniversalSession context, pass it as parameter

4. **Document lazy imports with comments**
   ```python
   def method(self):
       # Lazy import: Only needed when method is called
       from some.module import Something
   ```

5. **Test both Spark and DuckDB paths**
   - Some imports only happen on specific backend
   - Ensure fallbacks work for DuckDB-only environments

### Import Checklist

- [ ] All type hints use TYPE_CHECKING if optional
- [ ] No circular imports (run python -c "from models.api.session import UniversalSession")
- [ ] Lazy imports documented with comments
- [ ] Optional dependencies have try/except fallbacks
- [ ] No new imports at module level unless essential

---

## Summary

The UniversalSession achieves clean, circular-dependency-free architecture through:

1. **Early imports** for stable, essential dependencies (FilterEngine, StorageRouter)
2. **Lazy imports** for conditional, heavy dependencies (ModelRegistry, BaseModel)
3. **TYPE_CHECKING guards** for type-hint-only imports (PySpark types)
4. **Try/except fallbacks** for optional dependencies (YAML, PySpark)
5. **Unidirectional dependencies** (no upstream modules import downstream)

This design enables:
- Fast module load (minimal startup overhead)
- Memory efficiency (load what you use)
- Optional dependencies (DuckDB-only works fine)
- Clear separation of concerns
- Easy testing and maintenance
