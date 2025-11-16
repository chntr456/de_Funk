# Model Lifecycle

**Build process and lifecycle management**

Related: [BaseModel](../01-core-components/base-model.md) for implementation details

---

## Overview

Models in de_Funk follow a declarative lifecycle: define in YAML → build to Silver → query via Session.

```
YAML Config → Build Process → Silver Layer (Parquet) → Query Interface
```

---

## Lifecycle States

### 1. Defined (YAML)

Model exists as YAML configuration in `configs/models/`.

**State**: Configuration only, no data

**Operations**: Edit YAML, validate schema

---

### 2. Built (Silver Layer)

Model transformed from Bronze → Silver via `build()`.

**State**: Parquet files in `storage/silver/{model}/`

**Operations**: Query data, calculate measures

---

### 3. Loaded (In-Memory)

Model instantiated in Python session.

**State**: Python object with access to data

**Operations**: Execute measures, run queries, get tables

---

## Build Process

### build() Method Flow

```python
# BaseModel.build() orchestration
def build(self):
    # 1. Load Bronze data (raw tables)
    self._load_bronze_tables()

    # 2. Build graph nodes (dimensions & facts)
    self._build_nodes()

    # 3. Apply edges (validate joins)
    self._apply_edges()

    # 4. Materialize paths (create joined views)
    self._materialize_paths()

    # 5. Write to Silver
    self.write_tables()
```

---

### Build Order (Dependency Resolution)

Models must be built in dependency order:

**Tier 0**: core
**Tier 1**: macro, corporate
**Tier 2**: equity, city_finance
**Tier 3**: etf, forecast

**Automated via**:
```bash
python scripts/build_all_models.py  # Resolves dependencies automatically
```

---

## Common Operations

### Build Single Model

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model('equity')
model.build()  # Transforms Bronze → Silver
```

---

### Rebuild Model

```bash
# Clear Silver + rebuild
python scripts/rebuild_model.py --model equity
```

---

### Check if Built

```python
model.ensure_built()  # Lazy loading - builds if not built
```

---

## Build Lifecycle Hooks

Models can override hooks for custom logic:

```python
class EquityModel(BaseModel):
    def before_build(self):
        # Custom pre-processing
        self.validate_bronze_data()

    def after_build(self):
        # Custom post-processing
        self.create_indexes()
```

---

## Storage Layout

**Before build**:
```
storage/bronze/polygon/daily_prices/*.parquet  # Raw data
```

**After build**:
```
storage/silver/equity/
├── dims/
│   ├── dim_equity/*.parquet
│   └── dim_exchange/*.parquet
└── facts/
    └── fact_equity_prices/*.parquet
```

---

## Incremental vs Full Build

### Full Build
```python
model.build()  # Rebuilds all tables from Bronze
```

### Incremental Build
**Not yet supported** - all builds are currently full rebuilds

**Future**: Partition-based incremental updates

---

## Build Failures

**Common Issues**:

**Missing Bronze Data**:
```
Error: Bronze table 'polygon_daily_prices' not found
Solution: Run ingestion pipeline first
```

**Dependency Not Built**:
```
Error: Model 'corporate' not built (required by 'equity')
Solution: Build dependencies first or use build_all_models.py
```

**Schema Mismatch**:
```
Error: Column 'company_id' not found in dim_equity
Solution: Check YAML schema matches Bronze data
```

---

## Related Documentation

- [BaseModel](../01-core-components/base-model.md) - Build implementation
- [Dependency Resolution](../02-graph-architecture/dependency-resolution.md) - Build order
- [YAML Configuration](yaml-configuration.md) - Model definition format
