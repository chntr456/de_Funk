# Universal Session Architecture - Comprehensive Analysis

**Date**: November 21, 2025  
**Codebase**: de_Funk  
**Primary File**: `/home/user/de_Funk/models/api/session.py`  
**Related Files**: 
- `/home/user/de_Funk/core/session/filters.py`
- `/home/user/de_Funk/models/base/backend/adapter.py`
- `/home/user/de_Funk/models/base/backend/duckdb_adapter.py`
- `/home/user/de_Funk/models/base/backend/spark_adapter.py`
- `/home/user/de_Funk/models/api/graph.py`
- `/home/user/de_Funk/models/registry.py`

---

## Executive Summary

The **UniversalSession** is a model-agnostic database abstraction layer that provides:

1. **Unified Interface**: Single API for both DuckDB and Spark backends
2. **Dynamic Model Loading**: Runtime discovery and instantiation of any model
3. **Cross-Model Query**: Seamless queries across models with automatic joins
4. **Transparent Auto-Join**: Graph-based table relationship traversal
5. **Backend Abstraction**: Identical code works with different backends
6. **Filter Engine**: Centralized, backend-agnostic filter application
7. **Aggregation Support**: Automatic grain changes with measure-aware aggregation

### Key Strengths

- **Backend Agnostic**: Write query once, run on DuckDB or Spark
- **Graph-Based Dependencies**: Model relationships managed as DAG (Directed Acyclic Graph)
- **Session Injection**: Models can access each other through the session
- **Type-Safe Configuration**: All configuration is validated at load time
- **Lazy Loading**: Models and data loaded on demand for memory efficiency

---

## Architecture Overview

### Layered Design

```
┌─────────────────────────────────────────────────────────────┐
│                      User Code                              │
│  (Notebooks, Scripts, API endpoints)                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                  UniversalSession                           │
│  (models/api/session.py)                                    │
│  - Model loading & caching                                  │
│  - Cross-model join orchestration                           │
│  - Filter application coordination                          │
│  - Aggregation with measure awareness                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼──────────────┐
        │             │              │
┌───────▼──┐  ┌──────▼────┐  ┌──────▼──────┐
│  Filter  │  │  Model    │  │   Graph     │
│  Engine  │  │ Registry  │  │   Query     │
│          │  │           │  │  Planner    │
└───────┬──┘  └──────┬────┘  └──────┬──────┘
        │           │              │
        └───────────┼──────────────┘
                    │
        ┌───────────▼───────────┐
        │   BaseModel Class     │
        │ (models/base/model.py)│
        └───────────┬───────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼───┐    ┌─────▼────┐    ┌─────▼──────┐
│DuckDB │    │  Spark   │    │  Storage   │
│Adapter│    │ Adapter  │    │  Router    │
└───┬───┘    └─────┬────┘    └─────┬──────┘
    │              │               │
    └──────────────┼───────────────┘
                   │
        ┌──────────▼──────────┐
        │  Physical Storage   │
        │  (Parquet/Delta)    │
        └─────────────────────┘
```

---

## UniversalSession Class (Primary Component)

### Location
`/home/user/de_Funk/models/api/session.py` (Lines 47-1122)

### Class Definition

```python
class UniversalSession:
    """
    Model-agnostic session that works with any BaseModel.
    
    Key features:
    - Dynamic model loading from registry
    - Works with any model (company, forecast, etc.)
    - Cross-model queries and joins
    - Session injection for model dependencies
    """
```

### Constructor

**Method Signature:**
```python
def __init__(
    self,
    connection,                    # Database connection (Spark or DuckDB)
    storage_cfg: Dict[str, Any],   # Storage configuration {roots, tables}
    repo_root: Path,               # Repository root for absolute paths
    models: list[str] | None = None # Models to pre-load (optional)
)
```

**Initialization Steps:**
1. Stores connection, storage config, and repo root
2. Creates ModelRegistry from `configs/models/` directory
3. Initializes empty model cache `_models: Dict[str, Any]`
4. Builds ModelGraph for dependency tracking
5. Pre-loads specified models (if provided)

---

### Core Properties

#### `backend` Property (Lines 113-137)

```python
@property
def backend(self) -> str:
    """
    Detect backend type from connection.
    
    Returns:
        'spark' or 'duckdb'
    """
```

**Detection Logic:**
```
1. Get connection class name via str(type(self.connection))
2. Check for 'spark' → return 'spark'
3. Check for '_conn' attribute (DuckDB pattern) → return 'duckdb'
4. Otherwise → raise ValueError
```

---

### Main API Methods

#### 1. `load_model(model_name: str)` (Lines 183-232)

Dynamically loads a model and injects the session for cross-model access.

**Flow:**
```
1. Check cache → return if found
2. Get model config from registry
3. Get model class (or use BaseModel if not found)
4. Instantiate with:
   - connection
   - storage_cfg
   - model_cfg
   - params={}
   - repo_root
5. Inject session: model.set_session(self)
6. Cache instance
7. Return model
```

**Returns:** BaseModel instance (cached)

#### 2. `get_table(model_name, table_name, ...)` (Lines 262-405)

**Signature:**
```python
def get_table(
    self,
    model_name: str,
    table_name: str,
    required_columns: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    group_by: Optional[List[str]] = None,
    aggregations: Optional[Dict[str, str]] = None,
    use_cache: bool = True
) -> Any
```

**Behavior:**
- **No `required_columns`**: Returns full table with filters applied
- **All columns exist**: Selects columns, applies filters, aggregates if needed
- **Missing columns**: Uses auto-join strategies:
  1. Check for materialized view with all columns
  2. Build join plan from model graph
  3. Execute joins (Spark or DuckDB SQL)
  4. Apply filters (pushdown optimization)
  5. Apply aggregation to new grain if specified

**Returns:** DataFrame (Spark or DuckDB relation/Pandas)

#### 3. `get_filter_column_mappings(model_name, table_name)` (Lines 407-476)

Maps filter columns based on graph edges (e.g., `trade_date` → `metric_date`).

**Use Case:** Allows filters like 'trade_date' to apply to table-specific columns.

#### 4. `should_apply_cross_model_filter(source_model, target_model)` (Lines 143-181)

Determines if a filter from one model should apply to another.

**Logic:**
```
1. Same model? → Always True
2. Models related via graph? → True
3. Unrelated models? → False (conservative)
```

---

### Auto-Join Support Methods

#### `_plan_auto_joins()` (Lines 598-686)

Plans join sequence to retrieve missing columns using model graph.

**Output:**
```python
{
    'table_sequence': ['fact_prices', 'dim_company', 'dim_exchange'],
    'join_keys': [('ticker', 'ticker'), ('exchange_code', 'exchange_code')],
    'target_columns': {'exchange_name': 'dim_exchange'}
}
```

#### `_execute_auto_joins()` (Lines 730-891)

Executes join plan with backend-specific logic:

**Spark Path:** Uses DataFrame.join() API
```python
df = model.get_table(table_sequence[0])
for i, next_table in enumerate(table_sequence[1:]):
    right_df = model.get_table(next_table)
    left_col, right_col = join_keys[i]
    df = df.join(right_df, df[left_col] == right_df[right_col], 'left')
return df.select(*required_columns)
```

**DuckDB Path:** Uses SQL for efficiency
```sql
SELECT col1, col2 FROM _autojoin_fact_prices
LEFT JOIN _autojoin_dim_company ON fact_prices.ticker = dim_company.ticker
LEFT JOIN _autojoin_dim_exchange ON dim_company.exchange_code = dim_exchange.exchange_code
```

#### `_select_columns()` (Lines 525-557)

Backend-agnostic column selection:
- **Spark**: Uses `df.select(*columns)`
- **DuckDB**: Uses `df.project()` for relations or pandas filtering

#### `_find_materialized_view()` (Lines 559-596)

Searches for pre-computed views containing all required columns (performance optimization).

#### `_build_column_index()` (Lines 688-713)

Builds reverse index: `column_name → [table_names]` for join planning.

---

### Aggregation Methods

#### `_aggregate_data()` (Lines 893-945)

Aggregates data to new grain using group_by and measure metadata.

**Process:**
1. Identify measure columns (required_columns - group_by)
2. Load or infer aggregation functions
3. Apply backend-specific aggregation

#### `_infer_aggregations()` (Lines 947-984)

Infers aggregation functions from:
1. Model config measure definitions
2. Column name patterns (volume→sum, high→max, low→min, else→avg)

#### `_aggregate_spark()` (Lines 1013-1062)

Uses Spark groupBy/agg with F.avg(), F.sum(), F.max(), F.min(), F.count(), F.first()

#### `_aggregate_duckdb()` (Lines 1064-1121)

Uses SQL GROUP BY with aggregation functions, then converts to Pandas.

---

### Metadata Methods

#### `list_models()` (Lines 488-490)
Returns list of all available model names.

#### `list_tables(model_name)` (Lines 492-500)
Returns `{'dimensions': [...], 'facts': [...]}` for a model.

#### `get_model_metadata(model_name)` (Lines 502-505)
Returns model's metadata dictionary.

#### `get_model_instance(model_name)` (Lines 507-519)
Returns the loaded BaseModel instance (useful for model-specific methods).

---

## Filter Engine (Centralized)

### Location
`/home/user/de_Funk/core/session/filters.py` (Lines 24-316)

### Class: FilterEngine

**Purpose:** Unifies filter application across Spark and DuckDB.

#### Static Methods

##### `apply_filters(df, filters, backend)` (Lines 42-102)

Dispatches to backend-specific implementation.

**Filter Specification Formats:**

```python
# Exact match
{'ticker': 'AAPL'}

# IN clause (multiple values)
{'ticker': ['AAPL', 'GOOGL', 'MSFT']}

# Range filter
{
    'trade_date': {
        'min': '2024-01-01',
        'max': '2024-12-31',
        'operator': 'gte' | 'lte' | 'gt' | 'lt'
    }
}

# Combined
{
    'ticker': ['AAPL', 'GOOGL'],
    'trade_date': {'min': '2024-01-01'},
    'volume': {'min': 1000000}
}
```

##### `apply_from_session(df, filters, session)` (Lines 104-120)

Convenience method using session's backend detection.

```python
backend = session.backend
return FilterEngine.apply_filters(df, filters, backend)
```

##### `_apply_spark_filters()` (Lines 122-159)

Uses Spark SQL functions:
```python
# Range
df.filter(F.col(col_name) >= value['min'])
df.filter(F.col(col_name) <= value['max'])

# IN
df.filter(F.col(col_name).isin(value))

# Equality
df.filter(F.col(col_name) == value)
```

##### `_apply_duckdb_filters()` (Lines 161-262)

Handles both DuckDB relations and Pandas DataFrames:
```python
# DuckDB relation: builds SQL WHERE clause
where_clause = "ticker IN ('AAPL', 'GOOGL') AND volume >= 1000000"
df = df.filter(where_clause)

# Pandas DataFrame: uses boolean indexing
df = df[df['ticker'].isin(['AAPL', 'GOOGL'])]
df = df[df['volume'] >= 1000000]
```

##### `build_filter_sql()` (Lines 264-315)

Generates SQL WHERE clause from filters (useful for custom queries).

---

## Backend Adapters

### Abstract Base Class: BackendAdapter

**Location:** `models/base/backend/adapter.py` (Lines 26-173)

```python
class BackendAdapter(ABC):
    """
    Abstract interface for backend execution.
    
    All backends (DuckDB, Spark, Polars, etc.) must implement this.
    Measures generate SQL, adapters execute it in backend-specific way.
    """
```

#### Abstract Methods (must implement)

```python
@abstractmethod
def get_dialect(self) -> str:
    """Return 'duckdb', 'spark', etc."""

@abstractmethod
def execute_sql(self, sql: str, params: Optional[Dict] = None) -> QueryResult:
    """Execute SQL and return QueryResult with data + metadata."""

@abstractmethod
def get_table_reference(self, table_name: str) -> str:
    """
    Get backend-specific table reference:
    - DuckDB: "read_parquet('/path/to/table/*.parquet')"
    - Spark: "silver.fact_prices" or "parquet.`/path`"
    """

@abstractmethod
def supports_feature(self, feature: str) -> bool:
    """Check if backend supports SQL feature (window_functions, cte, etc.)"""
```

#### Helper Methods

```python
def format_limit(self, limit: int) -> str:
    """Format LIMIT clause (default: "LIMIT n")"""

def format_date_literal(self, date_str: str) -> str:
    """Format date literal (default: "DATE '2024-01-01'")"""

def get_null_safe_divide(self, numerator: str, denominator: str) -> str:
    """Null-safe division (default: "{num} / NULLIF({denom}, 0)")"""
```

### DuckDBAdapter

**Location:** `models/base/backend/duckdb_adapter.py` (Lines 18-243)

#### Key Features

- **Direct Parquet/Delta Reading**: Reads directly from files without loading
- **Delta Lake Support**: Detects and reads Delta tables
- **QUALIFY Clause**: Unique to DuckDB (filters after window functions)
- **Type Conversions**: Ensures Streamlit compatibility

#### Key Methods

```python
def get_dialect(self) -> str:
    return 'duckdb'

def execute_sql(self, sql: str, params=None) -> QueryResult:
    """Execute and return Pandas DataFrame"""

def get_table_reference(self, table_name: str) -> str:
    """
    Returns:
    - "read_parquet('/path/to/table/*.parquet')"
    - "delta_scan('/path')" for Delta tables
    - table_name if enriched via set_enriched_table()
    """

def supports_feature(self, feature: str) -> bool:
    supported = {
        'window_functions': True,
        'cte': True,
        'lateral_join': True,
        'array_agg': True,
        'qualify': True,        # DuckDB-specific!
        'delta_lake': True,
        'time_travel': True,
    }
```

#### Enrichment Support

```python
def set_enriched_table(self, table_name: str, enriched_df):
    """Register enriched DataFrame as view for auto-join optimization"""
    self.connection.conn.register(f"{table_name}_enriched", enriched_df)
    self.connection.execute(f"""
        CREATE OR REPLACE VIEW {table_name} AS
        SELECT * FROM {table_name}_enriched
    """)
```

### SparkAdapter

**Location:** `models/base/backend/spark_adapter.py` (Lines 19-250)

#### Key Features

- **Distributed Processing**: Uses lazy evaluation
- **Catalog-Based**: Integrates with Hive metastore
- **Table Caching**: In-memory caching for repeated access
- **Delta Lake Native**: First-class Delta Lake support

#### Key Methods

```python
def get_dialect(self) -> str:
    return 'spark'

def execute_sql(self, sql: str, params=None) -> QueryResult:
    """Execute and return Spark DataFrame (lazy)"""

def get_table_reference(self, table_name: str) -> str:
    """
    Returns:
    - "database.table_name" (catalog)
    - "delta.`/path`" (Delta table)
    - "parquet.`/path`" (Parquet table)
    - table_name if enriched via set_enriched_table()
    """

def supports_feature(self, feature: str) -> bool:
    supported = {
        'window_functions': True,
        'cte': True,
        'lateral_join': True,      # Spark 3.1+
        'array_agg': True,         # COLLECT_LIST
        'qualify': False,          # Not supported (use subquery)
        'pivot': True,
        'explode': True,           # Spark-specific
        'delta_lake': True,
        'time_travel': True,
    }
```

#### Caching Methods

```python
def cache_table(self, table_name: str):
    """Cache table in Spark memory"""
    self.connection.spark.sql(f"CACHE TABLE {table_name}")

def uncache_table(self, table_name: str):
    """Remove from cache"""
    self.connection.spark.sql(f"UNCACHE TABLE {table_name}")
```

---

## Model Registry & Discovery

### Location
`/home/user/de_Funk/models/registry.py`

### Class: ModelRegistry (Lines 263-529)

Discovers and manages all available models.

#### Key Methods

```python
def __init__(self, models_dir: Path):
    """
    Load all models from configs/models/ directory.
    Supports both modular (model.yaml) and legacy (.yaml) structures.
    """

def list_models(self) -> List[str]:
    """Return all available model names"""

def get_model_config(self, model_name: str) -> Dict:
    """
    Get raw model config dictionary (for model instantiation).
    Handles both modular and single-file YAML structures.
    """

def register_model_class(self, model_name: str, model_class: type):
    """Register Python class for dynamic instantiation"""

def get_model_class(self, model_name: str) -> type:
    """Get Python class, with lazy auto-registration by convention"""

def _try_auto_register(self, model_name: str):
    """
    Convention-based auto-registration:
    1. models.implemented.{model_name} (package import)
    2. models.implemented.{model_name}.model.{ModelName}Model
    """
```

---

## Model Graph Management

### Location
`/home/user/de_Funk/models/api/graph.py`

### Class: ModelGraph (Lines 21-422)

Manages model dependencies as a NetworkX directed acyclic graph (DAG).

#### Key Methods

```python
def build_from_config_dir(self, config_dir: Path):
    """Build graph from YAML config directory"""

def are_related(self, model_a: str, model_b: str) -> bool:
    """Check if models are directly or transitively related"""

def get_dependencies(self, model_name: str, transitive=False) -> Set[str]:
    """Get models this one depends on"""

def get_dependents(self, model_name: str, transitive=False) -> Set[str]:
    """Get models that depend on this one"""

def get_join_path(self, model_a: str, model_b: str) -> Optional[List[str]]:
    """Find shortest path between models"""

def get_build_order(self) -> List[str]:
    """Topological sort for build order (dependencies first)"""

def validate_no_cycles(self):
    """Ensure graph is a DAG (raises ValueError if cycles found)"""

def get_metrics(self) -> Dict[str, Any]:
    """Return graph statistics (nodes, edges, connectivity, etc.)"""
```

---

## Storage & Path Resolution

### Location
`/home/user/de_Funk/models/api/dal.py`

### Class: StorageRouter (Dataclass)

```python
@dataclass(frozen=True)
class StorageRouter:
    storage_cfg: Dict[str, Any]
    repo_root: Optional[Path] = None  # For absolute paths
    
    def bronze_path(self, logical_table: str) -> str:
        """Resolve bronze table path"""
        # Returns: "{repo_root}/storage/bronze/{rel}"
    
    def silver_path(self, logical_rel: str) -> str:
        """Resolve silver table path"""
        # Returns: "{repo_root}/storage/silver/{logical_rel}"
```

---

## Import Chain & Dependencies

### Core Imports (in session.py)

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Set, TYPE_CHECKING

# TYPE_CHECKING imports (optional, avoid circular deps)
if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame

# Core imports
from models.api.dal import StorageRouter, BronzeTable  # Path resolution
from core.session.filters import FilterEngine         # Filter application
from models.registry import ModelRegistry             # Model discovery
from models.api.graph import ModelGraph              # Dependency graph
```

### Dynamic Imports (lazy-loaded to avoid circular deps)

```python
# Inside __init__
from models.registry import ModelRegistry

# Inside load_model()
from models.base.model import BaseModel

# Inside backend detection
# (no additional imports needed)
```

### Dependency Tree

```
UniversalSession
├── ModelRegistry (models/registry.py)
│   ├── ModelConfig dataclass
│   ├── TableConfig dataclass
│   ├── MeasureConfig dataclass
│   └── Auto-registration logic
├── ModelGraph (models/api/graph.py)
│   └── NetworkX (nx)
├── FilterEngine (core/session/filters.py)
│   ├── PySpark functions (optional)
│   └── Pandas
├── StorageRouter (models/api/dal.py)
│   └── (No dependencies - dataclass)
└── BaseModel (models/base/model.py)
    ├── DuckDBAdapter / SparkAdapter
    ├── Storage router
    └── Connection (DuckDB/Spark)
```

### Circular Dependency Prevention

**Strategy:** Use `TYPE_CHECKING` and lazy imports

```python
# Top of file - avoid circular import
if TYPE_CHECKING:
    from pyspark.sql import DataFrame as SparkDataFrame

# In method body - only import when needed
def load_model(self, model_name: str):
    from models.base.model import BaseModel
    # Only imported when method is called, not at module load time
```

---

## Data Flow Examples

### Example 1: Simple Table Access

```
User Code
    ↓
session.get_table('stocks', 'fact_prices')
    ↓
1. load_model('stocks')
   - Registry.get_model_config('stocks')
   - Registry.get_model_class('stocks')
   - Instantiate StocksModel
   - Inject session
   - Cache in _models['stocks']
    ↓
2. _get_table_from_view_or_build()
   - Try connection.table('stocks.fact_prices') [DuckDB catalog]
   - Fall back to model.get_table('fact_prices')
    ↓
3. Return DataFrame
```

### Example 2: Auto-Join with Missing Columns

```
User Code
    ↓
session.get_table(
    'stocks', 
    'fact_prices',
    required_columns=['ticker', 'close', 'exchange_name']
)
    ↓
1. Check schema of 'fact_prices'
   - Base columns: ['ticker', 'close', 'volume', ...]
   - Missing: ['exchange_name']
    ↓
2. _find_materialized_view(['ticker', 'close', 'exchange_name'])
   - Search model tables for one with all columns
   - Not found → proceed to join planning
    ↓
3. _plan_auto_joins('stocks', 'fact_prices', ['exchange_name'])
   - Build column index: column → [tables]
   - Find 'exchange_name' in 'dim_exchange'
   - Plan path: fact_prices → dim_stock → dim_exchange
    ↓
4. _execute_auto_joins(join_plan, filters=None)
   [DuckDB Path]
   - Register temp tables: _autojoin_fact_prices, _autojoin_dim_stock, _autojoin_dim_exchange
   - Build SQL with LEFT JOINs
   - Execute SQL query
   - Convert result to DuckDB relation
   [Spark Path]
   - Get DataFrames
   - Chain df.join() calls
    ↓
5. Apply filters (if specified)
    ↓
6. Select columns: ['ticker', 'close', 'exchange_name']
    ↓
7. Return filtered, joined DataFrame
```

### Example 3: Cross-Model Filter Application

```
User Code
    ↓
session.get_table('stocks', 'fact_prices', filters={'ticker': ['AAPL', 'MSFT']})
    ↓
1. Load model
    ↓
2. Get table
    ↓
3. Apply filters:
   FilterEngine.apply_from_session(df, filters, session)
    ↓
4. Detect backend: session.backend
    ↓
5. [DuckDB path]
   - Build WHERE clause: "ticker IN ('AAPL', 'MSFT')"
   - Apply: df.filter("ticker IN ('AAPL', 'MSFT')")
   [Spark path]
   - Apply: df.filter(F.col('ticker').isin(['AAPL', 'MSFT']))
    ↓
6. Return filtered DataFrame
```

### Example 4: Aggregation to New Grain

```
User Code
    ↓
session.get_table(
    'stocks',
    'fact_prices',
    required_columns=['trade_date', 'exchange_name', 'close', 'volume'],
    group_by=['trade_date', 'exchange_name'],
    aggregations={'close': 'avg', 'volume': 'sum'}
)
    ↓
1. Get base table with auto-joins (if needed)
    ↓
2. Apply filters (if any)
    ↓
3. _aggregate_data(...)
    ↓
4. Determine measures: ['close', 'volume'] (require_cols - group_by)
    ↓
5. Verify aggregations from config:
   {'close': 'avg', 'volume': 'sum'}
    ↓
6. [DuckDB path]
   SQL: SELECT trade_date, exchange_name, AVG(close) as close, SUM(volume) as volume
        FROM df
        GROUP BY trade_date, exchange_name
   [Spark path]
   df.groupBy('trade_date', 'exchange_name').agg(F.avg('close'), F.sum('volume'))
    ↓
7. Return aggregated DataFrame
```

---

## Method Signatures Reference

### UniversalSession Public API

```python
class UniversalSession:
    # Initialization
    def __init__(
        self,
        connection,                    # Spark/DuckDB connection
        storage_cfg: Dict[str, Any],   # Storage config
        repo_root: Path,               # Repository root
        models: list[str] | None = None # Models to pre-load
    )
    
    # Properties
    @property
    def backend(self) -> str
    
    # Model Loading
    def load_model(self, model_name: str) -> Any  # Returns BaseModel
    
    # Table Access
    def get_table(
        self,
        model_name: str,
        table_name: str,
        required_columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None,
        use_cache: bool = True
    ) -> Any
    
    # Filter Column Mapping
    def get_filter_column_mappings(
        self,
        model_name: str,
        table_name: str
    ) -> Dict[str, str]
    
    # Cross-Model Filtering
    def should_apply_cross_model_filter(
        self,
        source_model: str,
        target_model: str
    ) -> bool
    
    # Table Access (Direct)
    def get_dimension_df(self, model_name: str, dim_id: str) -> Any
    def get_fact_df(self, model_name: str, fact_id: str) -> Any
    
    # Metadata
    def list_models(self) -> list[str]
    def list_tables(self, model_name: str) -> Dict[str, list[str]]
    def get_model_metadata(self, model_name: str) -> Dict[str, Any]
    def get_model_instance(self, model_name: str) -> Any
    
    # Private (for joins/aggregation)
    def _select_columns(self, df: Any, columns: List[str]) -> Any
    def _find_materialized_view(
        self,
        model_name: str,
        required_columns: List[str]
    ) -> Optional[str]
    def _plan_auto_joins(
        self,
        model_name: str,
        base_table: str,
        missing_columns: List[str]
    ) -> Dict[str, Any]
    def _build_column_index(self, model_name: str) -> Dict[str, List[str]]
    def _parse_join_condition(self, condition: str) -> Tuple[str, str]
    def _execute_auto_joins(
        self,
        model_name: str,
        join_plan: Dict[str, Any],
        required_columns: List[str],
        filters: Optional[Dict[str, Any]] = None
    ) -> Any
    def _aggregate_data(
        self,
        model_name: str,
        df: Any,
        required_columns: List[str],
        group_by: List[str],
        aggregations: Optional[Dict[str, str]] = None
    ) -> Any
    def _infer_aggregations(
        self,
        model_name: str,
        measure_cols: List[str]
    ) -> Dict[str, str]
    def _default_aggregation(self, column_name: str) -> str
    def _aggregate_spark(
        self,
        df: Any,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> Any
    def _aggregate_duckdb(
        self,
        df: Any,
        group_by: List[str],
        aggregations: Dict[str, str]
    ) -> Any
```

### FilterEngine Static Methods

```python
class FilterEngine:
    @staticmethod
    def apply_filters(
        df: Any,
        filters: Dict[str, Any],
        backend: str
    ) -> Any
    
    @staticmethod
    def apply_from_session(
        df: Any,
        filters: Dict[str, Any],
        session: UniversalSession
    ) -> Any
    
    @staticmethod
    def build_filter_sql(filters: Dict[str, Any]) -> str
    
    @staticmethod
    def _apply_spark_filters(df: Any, filters: Dict[str, Any]) -> Any
    
    @staticmethod
    def _apply_duckdb_filters(df: Any, filters: Dict[str, Any]) -> Any
```

---

## Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| `load_model()` | O(1) amortized | Cached after first load |
| `get_table()` simple | O(n) scan | Direct table read |
| `get_table()` with auto-join | O(n log n) | Hash joins in Spark/DuckDB |
| `_plan_auto_joins()` | O(e) | Graph traversal (e = edges) |
| Filter application | O(n) | Single pass through data |
| Aggregation | O(n log n) | Sort-based or hash aggregation |

### Space Complexity

| Component | Complexity | Notes |
|-----------|-----------|-------|
| Model cache | O(m) | m = number of loaded models |
| Graph storage | O(m + e) | m = models, e = edges |
| Column index | O(c) | c = total columns across tables |
| Filter expressions | O(f) | f = number of filter conditions |

### Optimization Strategies

1. **Lazy Loading**: Models loaded on demand, not all at startup
2. **Caching**: Models and column indexes cached after first access
3. **Filter Pushdown**: Filters applied before joins/aggregation
4. **Materialized Views**: Pre-computed joins used if available
5. **Backend Native Operations**: Uses Spark/DuckDB native APIs

---

## Error Handling & Edge Cases

### Common Errors

```python
# Backend detection fails
ValueError: "Unknown connection type: ..."
# Fix: Ensure connection is Spark session or DuckDB connection

# Model not found
ValueError: "Model 'xyz' not found. Available models: [...]"
# Fix: Check model name in configs/models/

# Table not found
ValueError: "Table 'fact_xyz' not found in model 'xyz' schema"
# Fix: Verify table in model YAML schema

# No join path
ValueError: "Cannot find join path from base_table to missing_columns"
# Fix: Add graph edges to connect tables

# Circular dependencies
ValueError: "Model dependency graph contains cycles: ..."
# Fix: Resolve circular dependencies in model configs
```

### Edge Cases Handled

1. **Empty filters**: Applied correctly (no-op)
2. **Missing required_columns**: Fall back to base table
3. **Unrelated models**: Conservative filter isolation
4. **Enriched tables**: Pre-computed joins prioritized
5. **Schema evolution**: Spark handles with `mergeSchema=true`

---

## Testing & Validation

### Test Examples

```python
# Test 1: Basic table access
session = UniversalSession(connection, storage_cfg, repo_root)
df = session.get_table('stocks', 'fact_prices')
assert df.count() > 0

# Test 2: Auto-join
df = session.get_table(
    'stocks', 'fact_prices',
    required_columns=['ticker', 'close', 'exchange_name']
)
assert 'exchange_name' in df.columns

# Test 3: Filter application
df = session.get_table(
    'stocks', 'fact_prices',
    filters={'ticker': 'AAPL'}
)
# Verify all rows have ticker='AAPL'

# Test 4: Aggregation
df = session.get_table(
    'stocks', 'fact_prices',
    group_by=['ticker'],
    aggregations={'volume': 'sum'}
)
# Verify one row per ticker

# Test 5: Cross-model relationships
assert session.should_apply_cross_model_filter('stocks', 'stocks')
assert session.should_apply_cross_model_filter('stocks', 'company')
assert not session.should_apply_cross_model_filter('stocks', 'unrelated')
```

---

## Best Practices

### Do

✅ Pre-load frequently used models
```python
session = UniversalSession(..., models=['stocks', 'company'])
```

✅ Use required_columns for explicit schema
```python
df = session.get_table('stocks', 'fact_prices', 
                       required_columns=['ticker', 'close'])
```

✅ Specify aggregations explicitly
```python
df = session.get_table('stocks', 'fact_prices',
                       group_by=['ticker'],
                       aggregations={'volume': 'sum'})
```

✅ Check backend before backend-specific code
```python
if session.backend == 'spark':
    df = df.repartition(10)
```

### Don't

❌ Load all models at startup (lazy load instead)
```python
# Bad
session = UniversalSession(..., models=[all 100 models])

# Good
session = UniversalSession(...)
model = session.load_model('xyz')  # On demand
```

❌ Mix backends in same code path
```python
# Bad - assumes Spark
df.collect()  # Fails on DuckDB

# Good - abstract
if session.backend == 'spark':
    results = df.collect()
else:
    results = df.to_pandas()
```

❌ Rely on auto-join for large joins
```python
# Bad - may be slow
df = session.get_table('stocks', 'fact_prices',
                       required_columns=[50 columns from 10 tables])

# Good - explicit materialized view or smaller queries
df = session.get_table('stocks', 'fact_prices_enriched')
```

---

## Conclusion

The **UniversalSession** is a well-architected abstraction layer that successfully:

1. **Hides backend differences**: Identical code works with Spark and DuckDB
2. **Manages model complexity**: Registry handles discovery and instantiation
3. **Enables cross-model access**: Graph manages dependencies, session injection enables communication
4. **Optimizes queries**: Filter pushdown, materialized views, lazy loading
5. **Maintains clarity**: Clear separation of concerns (filters, adapters, registry, graph)

The design demonstrates expert-level Python architecture with careful attention to:
- Avoiding circular imports (TYPE_CHECKING, lazy imports)
- Backend abstraction (Adapter pattern)
- Lazy evaluation and caching
- Error handling and edge cases
- Comprehensive documentation

**Key Innovation**: The combination of **UniversalSession + ModelGraph + FilterEngine** creates a remarkably elegant system where users can write simple queries that automatically handle complex multi-table joins and cross-model relationships.

