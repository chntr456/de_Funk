# Measure Framework Reference

**Unified calculation engine for all measure types**

Files:
- `models/base/measures/base_measure.py` - Abstract base class
- `models/base/measures/executor.py` - Execution engine
- `models/base/measures/registry.py` - Factory pattern
- `models/measures/simple.py` - Simple aggregations
- `models/measures/computed.py` - Expression-based
- `models/measures/weighted.py` - Weighted aggregations
- `models/base/backend/adapter.py` - Backend abstraction

---

## Overview

The Measure Framework provides a **declarative, YAML-driven system** for defining and executing business metrics across any backend (DuckDB, Spark, etc.).

### Key Features

- **YAML-Driven**: Define measures in model configuration, not code
- **Backend Agnostic**: Same measure works on DuckDB and Spark
- **Type System**: Support for simple, computed, weighted, window, ratio, custom measures
- **Auto-Enrichment**: Automatically joins required columns from related tables
- **SQL Generation**: Measures generate SQL, backends execute it
- **Unified Results**: QueryResult wrapper abstracts backend differences

### Design Philosophy

```
┌─────────────┐
│ YAML Config │ → Defines WHAT to calculate
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Measure   │ → Generates HOW (SQL)
│   Instance  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Backend   │ → Executes WHERE (DuckDB/Spark)
│   Adapter   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ QueryResult │ → Returns unified results
└─────────────┘
```

**Separation of Concerns:**
- **Measures**: Business logic (SQL generation)
- **Adapters**: Infrastructure (execution)
- **90% of measure code is backend-agnostic**

---

## Core Components

### BaseMeasure (Abstract Base Class)

**File:** `models/base/measures/base_measure.py:22-126`

Abstract base class defining the contract for all measure implementations.

#### Class Definition

```python
class BaseMeasure(ABC):
    """
    Abstract base class for all measure types.

    Measures are defined in YAML and instantiated via MeasureRegistry.
    """

    def __init__(self, config: Dict[str, Any]):
        self.name = config['name']
        self.description = config.get('description', '')
        self.source = config['source']  # 'table.column'
        self.data_type = config.get('data_type', 'double')
        self.format = config.get('format')
        self.tags = config.get('tags', [])
        self.auto_enrich = config.get('auto_enrich', False)

    @abstractmethod
    def to_sql(self, adapter) -> str:
        """Generate SQL for this measure."""
        pass

    def execute(self, adapter, **kwargs):
        """Execute measure using backend adapter."""
        sql = self.to_sql(adapter)
        return adapter.execute_sql(sql)
```

#### Common Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Measure identifier (added by registry) |
| `description` | str | Human-readable description |
| `source` | str | Source table and column (`table.column`) |
| `data_type` | str | Data type of result (default: `double`) |
| `format` | str | Output format (e.g., `$,.2f` for currency) |
| `tags` | list | Classification tags |
| `auto_enrich` | bool | Enable automatic table enrichment (joins) |

#### Public Methods

##### `to_sql(adapter) -> str`

Generate SQL for this measure (abstract method).

**Parameters:**
- `adapter` - BackendAdapter instance for dialect-specific SQL

**Returns:** SQL query string

**Raises:** `NotImplementedError` if measure cannot be expressed in SQL

**Example:**
```python
# Implemented by concrete measure classes
sql = measure.to_sql(duckdb_adapter)
# "SELECT AVG(close) as measure_value FROM read_parquet(...)"
```

---

##### `execute(adapter, **kwargs) -> QueryResult`

Execute measure using backend adapter.

**Parameters:**
- `adapter` - BackendAdapter instance
- `**kwargs` - Additional execution parameters

**Returns:** QueryResult with data and metadata

**Default Implementation:**
```python
def execute(self, adapter, **kwargs):
    sql = self.to_sql(adapter)
    return adapter.execute_sql(sql)
```

Can be overridden for measures requiring custom logic.

---

#### Protected Methods

##### `_parse_source() -> Tuple[str, str]`

Parse source into table and column.

**Returns:** Tuple of `(table_name, column_name)`

**Raises:** `ValueError` if source format is invalid

**Example:**
```python
# source = 'fact_equity_prices.close'
table, column = measure._parse_source()
# ('fact_equity_prices', 'close')
```

---

##### `_get_table_name() -> str`

Get table name from source.

**Returns:** Table name string

---

##### `_get_column_name() -> str`

Get column name from source.

**Returns:** Column name string

---

### MeasureType (Enum)

**File:** `models/base/measures/base_measure.py:12-20`

Enumeration of supported measure types.

```python
class MeasureType(Enum):
    SIMPLE = "simple"        # Direct aggregation (avg, sum, etc.)
    COMPUTED = "computed"    # Expression-based (close * volume)
    WEIGHTED = "weighted"    # Weighted aggregations
    WINDOW = "window"        # Window functions (rolling, lag, etc.)
    RATIO = "ratio"          # Ratios and percentages
    CUSTOM = "custom"        # Custom SQL/code
```

---

### MeasureRegistry

**File:** `models/base/measures/registry.py:12-160`

Registry for measure type implementations using the factory pattern.

#### Class Definition

```python
class MeasureRegistry:
    """
    Registry for measure type implementations.

    Uses decorator pattern for registering measure classes.
    Acts as a factory for creating measure instances from YAML config.
    """

    _registry: Dict[MeasureType, Type[BaseMeasure]] = {}
```

#### Class Methods

##### `@classmethod register(measure_type: MeasureType)`

Decorator to register measure implementations.

**Parameters:**
- `measure_type` - Type of measure this class implements

**Returns:** Decorator function

**Example:**
```python
@MeasureRegistry.register(MeasureType.SIMPLE)
class SimpleMeasure(BaseMeasure):
    def to_sql(self, adapter):
        # Implementation...
        pass
```

---

##### `@classmethod create_measure(config: Dict[str, Any]) -> BaseMeasure`

Factory method to create measure from configuration.

**Parameters:**
- `config` - Measure configuration dictionary from YAML

**Returns:** Instantiated measure object

**Raises:**
- `ValueError` - If measure type is unknown or not registered
- `KeyError` - If required config fields are missing

**Example:**
```python
config = {
    'name': 'avg_close',
    'type': 'simple',
    'source': 'fact_equity_prices.close',
    'aggregation': 'avg'
}
measure = MeasureRegistry.create_measure(config)
# Returns SimpleMeasure instance
```

---

##### `@classmethod get_registered_types() -> list`

Get list of registered measure types.

**Returns:** List of registered MeasureType enums

**Example:**
```python
types = MeasureRegistry.get_registered_types()
# [MeasureType.SIMPLE, MeasureType.COMPUTED, MeasureType.WEIGHTED]
```

---

##### `@classmethod is_registered(measure_type: MeasureType) -> bool`

Check if a measure type is registered.

**Parameters:**
- `measure_type` - Measure type to check

**Returns:** `True` if registered, `False` otherwise

---

##### `@classmethod get_measure_class(measure_type: MeasureType) -> Type[BaseMeasure]`

Get measure class for a given type.

**Parameters:**
- `measure_type` - Measure type

**Returns:** Measure class

**Raises:** `ValueError` if measure type not registered

---

### MeasureExecutor

**File:** `models/base/measures/executor.py:21-397`

Unified executor for all measure types.

#### Class Definition

```python
class MeasureExecutor:
    """
    Unified executor for all measure types.

    Provides single entry point for measure calculation,
    abstracting backend and measure type details.
    """

    def __init__(self, model, backend: str = 'duckdb'):
        self.model = model
        self.backend = backend
        self.adapter = self._create_adapter()
```

#### Constructor

##### `__init__(model, backend: str = 'duckdb')`

Initialize measure executor.

**Parameters:**
- `model` - Model instance (BaseModel or subclass)
- `backend` - Backend type (`'duckdb'` or `'spark'`)

**Example:**
```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model('equity')
executor = MeasureExecutor(model, backend='duckdb')
```

---

#### Public Methods

##### `execute_measure(measure_name, entity_column=None, filters=None, limit=None, **kwargs) -> QueryResult`

Execute a measure from model configuration.

**Main entry point for measure execution.** Works with ANY measure type and ANY backend!

**Parameters:**
- `measure_name` - Name of measure from model config
- `entity_column` - Optional entity column to group by
- `filters` - Optional filters to apply (dict or list)
- `limit` - Optional limit for results
- `**kwargs` - Additional measure-specific parameters

**Returns:** QueryResult with data and metadata

**Raises:** `ValueError` if measure not defined in model config

**Examples:**

**Simple Measure:**
```python
# Average close price by ticker
result = executor.execute_measure(
    'avg_close_price',
    entity_column='ticker'
)

# Result: DataFrame with columns [ticker, measure_value]
```

**Weighted Measure:**
```python
# Volume-weighted index
result = executor.execute_measure('volume_weighted_index')

# Result: DataFrame with columns [trade_date, measure_value]
```

**With Filters:**
```python
# Average close for AAPL in 2024
result = executor.execute_measure(
    'avg_close_price',
    filters={'ticker': 'AAPL', 'trade_date': {'start': '2024-01-01'}},
    limit=10
)
```

**With Auto-Enrichment:**
```python
# Average close by exchange (exchange_name not in fact_equity_prices!)
# auto_enrich=True in measure config enables dynamic join
result = executor.execute_measure(
    'avg_close_by_exchange',
    entity_column='exchange_name'
)

# MeasureExecutor automatically:
# 1. Detects exchange_name is not in fact_equity_prices
# 2. Uses query planner to find join path
# 3. Enriches table with exchange_name column
# 4. Executes measure
```

---

##### `list_measures() -> Dict[str, Dict[str, Any]]`

List all available measures in model.

**Returns:** Dictionary of measure name → measure config

**Example:**
```python
measures = executor.list_measures()
# {
#     'avg_close_price': {
#         'type': 'simple',
#         'source': 'fact_equity_prices.close',
#         'aggregation': 'avg',
#         ...
#     },
#     'volume_weighted_index': {
#         'type': 'weighted',
#         'source': 'fact_equity_prices.close',
#         'weighting_method': 'volume',
#         ...
#     }
# }
```

---

##### `get_measure_info(measure_name: str) -> Dict[str, Any]`

Get information about a specific measure.

**Parameters:**
- `measure_name` - Name of measure

**Returns:** Dictionary with measure metadata

**Raises:** `ValueError` if measure not found

**Example:**
```python
info = executor.get_measure_info('avg_close_price')
# {
#     'name': 'avg_close_price',
#     'type': 'simple',
#     'description': 'Average closing price',
#     'source': 'fact_equity_prices.close',
#     'data_type': 'double',
#     'tags': ['price', 'equity']
# }
```

---

##### `explain_measure(measure_name: str) -> str`

Generate SQL for a measure without executing it.

Useful for debugging and optimization.

**Parameters:**
- `measure_name` - Name of measure

**Returns:** SQL query string

**Example:**
```python
sql = executor.explain_measure('volume_weighted_index')
print(sql)

# Output:
# SELECT
#     trade_date,
#     SUM(close * volume) / SUM(volume) as measure_value
# FROM read_parquet('/path/to/fact_equity_prices/*.parquet')
# WHERE close IS NOT NULL AND volume IS NOT NULL
# GROUP BY trade_date
# ORDER BY trade_date
```

---

#### Protected Methods

##### `_create_adapter() -> BackendAdapter`

Factory method for backend adapters.

**Returns:** Backend-specific adapter instance

**Raises:** `ValueError` if backend is not supported

---

##### `_get_measure_config(measure_name: str) -> Dict[str, Any]`

Get measure configuration from model.

**Parameters:**
- `measure_name` - Name of measure

**Returns:** Measure configuration dictionary

**Raises:** `ValueError` if measure not found

---

##### `_auto_enrich_measure(...)`

Automatically enrich measure source table with columns from related tables.

Uses GraphQueryPlanner to find and join required tables when columns are not available in the base source table.

**Auto-Enrichment Process:**

1. Collect all required columns (source, entity, group_by, weights, filters)
2. Get schema for base table
3. Find columns not in base table
4. Use query planner to find tables with missing columns
5. Build join paths from base table to target tables
6. Get enriched table with all columns
7. Update adapter to use enriched table

**Example:**

```yaml
# Measure config
avg_close_by_exchange:
  source: fact_equity_prices.close
  entity_column: exchange_name  # Not in fact_equity_prices!
  auto_enrich: true
```

```python
# Auto-enrichment process:
# 1. Detect exchange_name not in fact_equity_prices
# 2. Find path: fact_equity_prices -> dim_equity -> dim_exchange
# 3. Get enriched table with exchange_name
# 4. Execute measure on enriched table
```

---

##### `_get_table_schema(table_name: str) -> Optional[Dict[str, str]]`

Get schema for a table from model config.

**Parameters:**
- `table_name` - Table name

**Returns:** Dictionary of column_name → data_type, or None if not found

---

## Measure Types

### SimpleMeasure

**File:** `models/measures/simple.py:14-255`

Simple aggregation measure for direct aggregations.

#### YAML Configuration

```yaml
avg_close_price:
  type: simple
  source: fact_equity_prices.close
  aggregation: avg
  data_type: double
  description: Average closing price
```

#### Supported Aggregations

- `avg` - Average
- `sum` - Sum
- `min` - Minimum
- `max` - Maximum
- `count` - Count
- `stddev` - Standard deviation
- `variance` - Variance

#### Constructor

```python
def __init__(self, config: Dict[str, Any]):
    super().__init__(config)
    self.aggregation = config.get('aggregation', 'avg').upper()
```

#### Methods

##### `to_sql(adapter) -> str`

Generate SQL for simple aggregation.

**Example Output:**
```sql
SELECT
    AVG(close) as measure_value
FROM read_parquet('/path/to/fact_equity_prices/*.parquet')
WHERE close IS NOT NULL
```

---

##### `execute(adapter, entity_column=None, filters=None, limit=None, **kwargs) -> QueryResult`

Execute simple measure with optional grouping.

**Parameters:**
- `adapter` - Backend adapter
- `entity_column` - Optional column to group by
- `filters` - Optional WHERE clause conditions (dict or list)
- `limit` - Optional result limit
- `**kwargs` - Additional filter parameters

**Examples:**

**Ungrouped:**
```python
result = measure.execute(adapter)
# Overall average
```

**Grouped:**
```python
result = measure.execute(adapter, entity_column='ticker')
# Average per ticker
```

**With Filters:**
```python
result = measure.execute(
    adapter,
    entity_column='ticker',
    filters={'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}},
    limit=10
)
# Top 10 tickers by average close in 2024
```

**With Kwargs Filters:**
```python
result = measure.execute(
    adapter,
    entity_column='ticker',
    trade_date={'start': '2024-01-01', 'end': '2024-12-31'},
    ticker=['AAPL', 'MSFT', 'GOOGL']
)
# Average for specific tickers in date range
```

---

#### Filter Specification Format

SimpleMeasure supports flexible filter specifications:

**Exact Match:**
```python
filters = {'ticker': 'AAPL'}
# SQL: ticker = 'AAPL'
```

**IN Clause:**
```python
filters = {'ticker': ['AAPL', 'MSFT', 'GOOGL']}
# SQL: ticker IN ('AAPL', 'MSFT', 'GOOGL')
```

**Date Range:**
```python
filters = {
    'trade_date': {
        'start': '2024-01-01',
        'end': '2024-12-31'
    }
}
# SQL: trade_date >= '2024-01-01' AND trade_date <= '2024-12-31'
```

**Numeric Range:**
```python
filters = {
    'close': {
        'gte': 100,
        'lte': 200
    }
}
# SQL: close >= 100 AND close <= 200
```

**Comparison Operators:**
```python
filters = {
    'close': {'gt': 100},   # close > 100
    'volume': {'lt': 1000}  # volume < 1000
}
```

---

### ComputedMeasure

**File:** `models/measures/computed.py:14-165`

Computed measure using custom expressions.

#### YAML Configuration

```yaml
market_cap:
  type: computed
  source: fact_equity_prices.close
  expression: "close * volume"
  aggregation: avg
  data_type: double
  description: Average market capitalization
```

#### Constructor

```python
def __init__(self, config: Dict[str, Any]):
    super().__init__(config)
    self.expression = config.get('expression')
    self.aggregation = config.get('aggregation', 'avg').upper()
```

#### Methods

##### `to_sql(adapter) -> str`

Generate SQL for computed measure.

**Example Output:**
```sql
SELECT
    AVG(close * volume) as measure_value
FROM read_parquet('/path/to/fact_equity_prices/*.parquet')
WHERE close IS NOT NULL AND volume IS NOT NULL
```

---

##### `execute(adapter, entity_column=None, filters=None, limit=None, **kwargs) -> QueryResult`

Execute computed measure with optional grouping.

**Example:**
```python
# Compute average market cap by ticker
result = measure.execute(adapter, entity_column='ticker')

# With filters
result = measure.execute(
    adapter,
    entity_column='ticker',
    filters={'trade_date': {'start': '2024-01-01'}},
    limit=10
)
```

---

### WeightedMeasure

**File:** `models/measures/weighted.py:13-113`

Weighted aggregate measure.

Calculates weighted aggregations across multiple entities using various weighting schemes.

#### YAML Configuration

```yaml
volume_weighted_index:
  type: weighted
  source: fact_equity_prices.close
  weighting_method: volume
  group_by: [trade_date]
  data_type: double
  description: Volume-weighted price index
```

#### Constructor

```python
def __init__(self, config: Dict[str, Any]):
    super().__init__(config)
    self.weighting_method = config.get('weighting_method', 'equal')
    self.group_by = config.get('group_by', ['trade_date'])
    self.weight_column = config.get('weight_column')  # Optional explicit weights
    self.measure_filters = config.get('filters', [])
```

#### Weighting Methods

- `equal` - Equal weighting (simple average)
- `volume` - Volume-weighted
- `market_cap` - Market capitalization weighted
- `custom` - Custom weight column

#### Methods

##### `to_sql(adapter) -> str`

Generate SQL for weighted aggregate.

Delegates to domain-specific weighting strategy.

**Example Output:**
```sql
SELECT
    trade_date,
    SUM(close * volume) / SUM(volume) as measure_value
FROM read_parquet('/path/to/fact_equity_prices/*.parquet')
WHERE close IS NOT NULL AND volume IS NOT NULL
GROUP BY trade_date
ORDER BY trade_date
```

---

##### `execute(adapter, filters=None, **kwargs) -> QueryResult`

Execute weighted measure.

**Parameters:**
- `adapter` - Backend adapter
- `filters` - Optional additional filters (merged with measure filters)
- `**kwargs` - Additional parameters

**Example:**
```python
# Compute volume-weighted index
result = measure.execute(adapter)

# With filters
result = measure.execute(
    adapter,
    filters={'trade_date': {'start': '2024-01-01'}}
)
```

---

## Backend Adapters

### BackendAdapter (Abstract)

**File:** `models/base/backend/adapter.py:26-173`

Abstract interface for backend execution.

#### Class Definition

```python
class BackendAdapter(ABC):
    """
    Abstract interface for backend execution.

    Measures generate SQL, adapters execute it in a backend-specific way.
    """

    def __init__(self, connection, model):
        self.connection = connection
        self.model = model
        self.dialect = self.get_dialect()
```

#### Abstract Methods

##### `get_dialect() -> str`

Get SQL dialect name.

**Returns:** Dialect name (e.g., `'duckdb'`, `'spark'`, `'postgres'`)

---

##### `execute_sql(sql: str, params=None) -> QueryResult`

Execute SQL query and return results.

**Parameters:**
- `sql` - SQL query string
- `params` - Optional query parameters for parameterized queries

**Returns:** QueryResult with data and metadata

**Raises:** Exception if query execution fails

---

##### `get_table_reference(table_name: str) -> str`

Get backend-specific table reference.

Different backends access tables differently:
- **DuckDB**: `"read_parquet('/path/to/table/*.parquet')"`
- **Spark**: `"silver.fact_prices"`
- **Postgres**: `"silver.fact_prices"`

**Parameters:**
- `table_name` - Logical table name from model schema

**Returns:** Backend-specific table reference string

**Raises:** `ValueError` if table not found in model schema

---

##### `supports_feature(feature: str) -> bool`

Check if backend supports a SQL feature.

**Features:**
- `'window_functions'` - Window functions (ROW_NUMBER, LAG, etc.)
- `'cte'` - Common Table Expressions (WITH clause)
- `'lateral_join'` - LATERAL joins
- `'qualify'` - QUALIFY clause (DuckDB-specific)
- `'array_agg'` - ARRAY_AGG function

**Parameters:**
- `feature` - Feature name

**Returns:** `True` if feature is supported, `False` otherwise

---

#### Helper Methods

##### `format_limit(limit: int) -> str`

Format LIMIT clause (backend-specific).

**Returns:** Formatted LIMIT clause (e.g., `"LIMIT 10"`)

---

##### `format_date_literal(date_str: str) -> str`

Format date literal (backend-specific).

**Parameters:**
- `date_str` - Date string in ISO format (YYYY-MM-DD)

**Returns:** Backend-specific date literal (e.g., `"DATE '2024-01-01'"`)

---

##### `format_column_alias(column: str, alias: str) -> str`

Format column with alias.

**Returns:** Formatted column with alias (e.g., `"close as price"`)

---

##### `get_null_safe_divide(numerator: str, denominator: str) -> str`

Get null-safe division expression.

Prevents division by zero and handles nulls.

**Returns:** Null-safe division expression (e.g., `"close / NULLIF(volume, 0)"`)

---

### QueryResult

**File:** `models/base/backend/adapter.py:12-24`

Unified query result wrapper.

Encapsulates query results with metadata regardless of backend.

```python
@dataclass
class QueryResult:
    data: Any              # DataFrame (Pandas, Spark, etc.)
    backend: str           # Backend name ('duckdb', 'spark')
    query_time_ms: float   # Query execution time in milliseconds
    rows: int              # Number of rows returned
    sql: Optional[str]     # Original SQL query
```

---

## Usage Patterns

### Basic Measure Execution

```python
from core.context import RepoContext
from models.api.registry import get_model_registry
from models.base.measures.executor import MeasureExecutor

# Get model
ctx = RepoContext.from_repo_root(connection_type='duckdb')
registry = get_model_registry()
model = registry.get_model('equity')

# Create executor
executor = MeasureExecutor(model, backend='duckdb')

# Execute measure
result = executor.execute_measure(
    'avg_close_price',
    entity_column='ticker',
    limit=10
)

# Access results
print(result.data)  # Pandas DataFrame
print(f"Rows: {result.rows}, Time: {result.query_time_ms}ms")
```

---

### Listing Available Measures

```python
# List all measures
measures = executor.list_measures()

for name, config in measures.items():
    print(f"{name}: {config.get('description', '')}")

# Get measure info
info = executor.get_measure_info('avg_close_price')
print(f"Type: {info['type']}, Source: {info['source']}")
```

---

### Debugging with explain_measure

```python
# Generate SQL without executing
sql = executor.explain_measure('volume_weighted_index')
print(sql)

# View generated SQL for debugging
print("Generated SQL:")
print("-" * 80)
print(sql)
print("-" * 80)
```

---

### Executing with Filters

```python
# Date range filter
result = executor.execute_measure(
    'avg_close_price',
    entity_column='ticker',
    filters={
        'trade_date': {'start': '2024-01-01', 'end': '2024-12-31'}
    }
)

# Multiple filters
result = executor.execute_measure(
    'avg_close_price',
    entity_column='ticker',
    trade_date={'start': '2024-01-01'},
    ticker=['AAPL', 'MSFT', 'GOOGL'],
    limit=10
)
```

---

### Auto-Enrichment Example

```yaml
# Model config: equity.yaml
measures:
  avg_close_by_exchange:
    type: simple
    source: fact_equity_prices.close
    aggregation: avg
    auto_enrich: true
```

```python
# Execute measure - automatically joins required tables
result = executor.execute_measure(
    'avg_close_by_exchange',
    entity_column='exchange_name'  # Not in fact_equity_prices!
)

# MeasureExecutor:
# 1. Detects exchange_name missing
# 2. Finds path: fact_equity_prices -> dim_equity -> dim_exchange
# 3. Enriches table with join
# 4. Executes measure
```

---

### Backend Comparison

```python
# DuckDB execution
duckdb_executor = MeasureExecutor(model, backend='duckdb')
duckdb_result = duckdb_executor.execute_measure('avg_close_price')

# Spark execution
spark_executor = MeasureExecutor(model, backend='spark')
spark_result = spark_executor.execute_measure('avg_close_price')

# Same measure, different backends!
print(f"DuckDB: {duckdb_result.query_time_ms}ms")
print(f"Spark: {spark_result.query_time_ms}ms")
```

---

### Creating Custom Measures

```python
# Register custom measure type
from models.base.measures.base_measure import BaseMeasure, MeasureType
from models.base.measures.registry import MeasureRegistry

@MeasureRegistry.register(MeasureType.CUSTOM)
class CustomMeasure(BaseMeasure):
    def to_sql(self, adapter):
        table_ref = adapter.get_table_reference(self._get_table_name())
        return f"SELECT custom_logic(...) FROM {table_ref}"
```

---

## YAML Configuration Examples

### Simple Measure

```yaml
avg_close_price:
  type: simple
  source: fact_equity_prices.close
  aggregation: avg
  data_type: double
  description: Average closing price
  tags: [price, equity]
```

### Computed Measure

```yaml
daily_dollar_volume:
  type: computed
  source: fact_equity_prices.close
  expression: "close * volume"
  aggregation: sum
  data_type: double
  description: Total dollar volume traded
  tags: [volume, trading]
```

### Weighted Measure

```yaml
volume_weighted_price:
  type: weighted
  source: fact_equity_prices.close
  weighting_method: volume
  group_by: [trade_date]
  data_type: double
  description: Volume-weighted average price
  tags: [index, weighted]
```

### Measure with Auto-Enrichment

```yaml
avg_close_by_sector:
  type: simple
  source: fact_equity_prices.close
  aggregation: avg
  auto_enrich: true
  description: Average close price by sector (requires join)
  tags: [price, sector]
```

### Measure with Filters

```yaml
avg_close_large_cap:
  type: simple
  source: fact_equity_prices.close
  aggregation: avg
  filters:
    - "market_cap > 10000000000"
  description: Average close for large cap stocks
  tags: [price, large_cap]
```

---

## Backend Implementation Comparison

| Feature | DuckDB | Spark |
|---------|--------|-------|
| **SQL Generation** | Yes | Yes |
| **Table Reference** | `read_parquet('/path/*.parquet')` | `silver.table_name` |
| **Window Functions** | Yes | Yes |
| **CTEs** | Yes | Yes |
| **QUALIFY Clause** | Yes | No |
| **LATERAL Joins** | Yes | Limited |
| **Execution** | In-process | Distributed |
| **Auto-Enrichment** | Yes | Yes |

---

## Execution Flow

```
1. User calls execute_measure()
   ↓
2. MeasureExecutor._get_measure_config()
   - Load measure config from model YAML
   ↓
3. MeasureRegistry.create_measure()
   - Instantiate measure object (Simple/Computed/Weighted)
   ↓
4. Check auto_enrich flag
   ↓
5. If auto_enrich=True:
   - MeasureExecutor._auto_enrich_measure()
   - Collect required columns
   - Find missing columns
   - Use QueryPlanner to build join paths
   - Get enriched table
   - Update adapter with enriched table
   ↓
6. Measure.execute(adapter, **kwargs)
   ↓
7. Measure.to_sql(adapter)
   - Generate SQL query
   ↓
8. BackendAdapter.execute_sql(sql)
   - Execute query on backend
   ↓
9. Return QueryResult
   - Data (DataFrame)
   - Metadata (rows, query_time, etc.)
```

---

## Best Practices

1. **Use YAML for measures**: Define in model config, not code
2. **Enable auto_enrich**: Let framework handle joins automatically
3. **Group by entity column**: Get per-entity metrics (ticker, date, etc.)
4. **Apply filters early**: Push filters into SQL for performance
5. **Use explain_measure**: Debug SQL generation
6. **Tag your measures**: Organize with tags (price, volume, index, etc.)
7. **Choose appropriate aggregation**: avg, sum, min, max based on semantics
8. **Use QueryResult metadata**: Track query performance

---

## Troubleshooting

### Measure Not Found

**Error:** `Measure 'avg_close' not defined in model 'equity'`

**Solution:** Check measure exists in `configs/models/equity.yaml`

---

### Invalid Aggregation

**Error:** `Invalid aggregation 'average'. Valid: ['AVG', 'SUM', 'MIN', 'MAX', ...]`

**Solution:** Use uppercase aggregation name: `avg` not `average`

---

### Missing Column in Source Table

**Error:** `Column 'exchange_name' not found in fact_equity_prices`

**Solution:** Enable auto-enrichment:
```yaml
measure_name:
  auto_enrich: true
```

---

### Backend Not Supported

**Error:** `Unsupported backend: 'postgres'`

**Solution:** Use `'duckdb'` or `'spark'`

---

### Expression Parsing Error

**Error:** `Failed to parse expression 'close * volume'`

**Solution:** Check expression syntax is valid SQL

---

## Related Documentation

- [BaseModel](../01-core-components/base-model.md) - Model framework using measures
- [UniversalSession](../01-core-components/universal-session.md) - Query interface
- [Connection System](../01-core-components/connection-system.md) - Backend connections
- [YAML Configuration](yaml-configuration.md) - Model configuration format
