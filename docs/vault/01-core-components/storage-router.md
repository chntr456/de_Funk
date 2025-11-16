# StorageRouter & Data Access Layer Reference

**Path management for Bronze and Silver layers**

File: `models/api/dal.py`

---

## Overview

The Data Access Layer (DAL) provides simple utilities for managing storage paths and reading Bronze/Silver tables. It consists of three small classes that handle path resolution and data loading.

### Key Components

- **StorageRouter**: Resolves Bronze and Silver storage paths
- **BronzeTable**: Reads raw data from Bronze layer with schema merging
- **SilverPath**: Reads dimensional models from Silver layer

### Design Patterns

- **Dataclass**: StorageRouter is immutable (frozen)
- **Path Abstraction**: Separates logical table names from physical paths
- **Configuration-Driven**: Uses `storage.json` configuration

---

## StorageRouter

**File:** `models/api/dal.py:7-18`

Immutable dataclass that resolves storage paths based on configuration.

### Class Definition

```python
@dataclass(frozen=True)
class StorageRouter:
    storage_cfg: Dict[str, Any]
```

**Attributes:**
- `storage_cfg` - Storage configuration dict (from `storage.json`)

**Immutability:** Frozen dataclass ensures configuration cannot be modified after creation

---

### Methods

#### `bronze_path(logical_table: str) -> str`

Resolve Bronze layer path for a logical table.

**Parameters:**
- `logical_table` - Logical table name (key in `storage.json`)

**Returns:** Full path to Bronze table

**Logic:**
1. Get Bronze root from `storage_cfg["roots"]["bronze"]`
2. Get relative path from `storage_cfg["tables"][logical_table]["rel"]`
3. Combine: `{root}/{rel}`

**Example:**
```python
router = StorageRouter(storage_cfg)

# Resolve path for "prices_daily" table
path = router.bronze_path("prices_daily")
# Returns: "storage/bronze/polygon/prices_daily"
```

**Configuration:**
```json
{
  "roots": {
    "bronze": "storage/bronze"
  },
  "tables": {
    "prices_daily": {
      "rel": "polygon/prices_daily"
    }
  }
}
```

---

#### `silver_path(logical_rel: str) -> str`

Resolve Silver layer path for a logical relation.

**Parameters:**
- `logical_rel` - Logical path relative to Silver root (e.g., "equity/dims/dim_equity")

**Returns:** Full path to Silver table

**Logic:**
1. Get Silver root from `storage_cfg["roots"]["silver"]`
2. Combine: `{root}/{logical_rel}`

**Example:**
```python
router = StorageRouter(storage_cfg)

# Resolve path for equity dimension
path = router.silver_path("equity/dims/dim_equity")
# Returns: "storage/silver/equity/dims/dim_equity"
```

---

## BronzeTable

**File:** `models/api/dal.py:20-46`

Reads Bronze tables from Parquet with schema merging support.

### Class Constructor

#### `__init__(spark: SparkSession, router: StorageRouter, logical_table: str)`

Initialize Bronze table reader.

**Parameters:**
- `spark` - Spark session for reading Parquet
- `router` - StorageRouter for path resolution
- `logical_table` - Logical table name

**Example:**
```python
bronze = BronzeTable(spark, router, "prices_daily")
```

---

### Properties

#### `path` (property)

Get physical path to Bronze table.

**Returns:** Full path string

**Example:**
```python
bronze = BronzeTable(spark, router, "prices_daily")
print(bronze.path)
# "storage/bronze/polygon/prices_daily"
```

---

### Methods

#### `read(merge_schema: bool = True) -> DataFrame`

Read Bronze table from Parquet.

**Parameters:**
- `merge_schema` - If True, merges schemas across partitions (default: True)

**Returns:** Spark DataFrame

**Schema Merging:**
- Prevents `CANNOT_DETERMINE_TYPE` errors
- Handles schema evolution across partitions
- Different partitions can have slightly different schemas

**Example:**
```python
bronze = BronzeTable(spark, router, "prices_daily")

# Read with schema merging (default)
df = bronze.read()

# Read without schema merging
df = bronze.read(merge_schema=False)
```

**When to use schema merging:**
- **True** (default): API data that may evolve over time
- **False**: Known stable schema for performance

---

## SilverPath

**File:** `models/api/dal.py:48-71`

Reads Silver tables from Parquet or in-memory DataFrames.

### Class Constructor

#### `__init__(spark: SparkSession, router: StorageRouter, logical_rel: str)`

Initialize Silver path reader.

**Parameters:**
- `spark` - Spark session for reading Parquet
- `router` - StorageRouter for path resolution
- `logical_rel` - Logical path relative to Silver root

**Example:**
```python
silver = SilverPath(spark, router, "equity/dims/dim_equity")
```

---

### Properties

#### `path` (property)

Get physical path to Silver table.

**Returns:** Full path string

**Example:**
```python
silver = SilverPath(spark, router, "equity/facts/fact_equity_prices")
print(silver.path)
# "storage/silver/equity/facts/fact_equity_prices"
```

---

### Methods

#### `read() -> DataFrame`

Read Silver table from Parquet or override DataFrame.

**Returns:** Spark DataFrame

**Logic:**
1. If override DataFrame set via `set_df()`, return that
2. Otherwise, read from Parquet at `path`

**Example:**
```python
silver = SilverPath(spark, router, "equity/dims/dim_equity")

# Read from Parquet
df = silver.read()
```

---

#### `set_df(df: DataFrame)`

Set override DataFrame (for in-memory usage).

**Parameters:**
- `df` - Spark DataFrame to use instead of reading from Parquet

**Use Case:**
- Keep silver outputs in-memory instead of writing to Parquet
- Override persisted data with modified version
- Testing

**Example:**
```python
silver = SilverPath(spark, router, "equity/dims/dim_equity")

# Use in-memory DataFrame
silver.set_df(my_df)

# Now read() returns my_df instead of reading from Parquet
df = silver.read()  # Returns my_df
```

---

## Usage Patterns

### Basic Path Resolution

```python
from models.api.dal import StorageRouter

# Load storage configuration
with open('configs/storage.json') as f:
    storage_cfg = json.load(f)

# Create router
router = StorageRouter(storage_cfg)

# Resolve paths
bronze_path = router.bronze_path("prices_daily")
silver_path = router.silver_path("equity/dims/dim_equity")
```

### Reading Bronze Data

```python
from models.api.dal import BronzeTable
from pyspark.sql import SparkSession

# Create Spark session
spark = SparkSession.builder.getOrCreate()

# Create router
router = StorageRouter(storage_cfg)

# Read Bronze table
bronze = BronzeTable(spark, router, "prices_daily")
df = bronze.read(merge_schema=True)

print(f"Loaded {df.count()} rows from {bronze.path}")
```

### Reading Silver Data

```python
from models.api.dal import SilverPath

# Create router
router = StorageRouter(storage_cfg)

# Read Silver table
silver = SilverPath(spark, router, "equity/dims/dim_equity")
df = silver.read()

print(f"Loaded dimension from {silver.path}")
```

### In-Memory Silver Tables

```python
# Build dimension in-memory
dim_equity = build_equity_dimension()

# Create SilverPath with override
silver = SilverPath(spark, router, "equity/dims/dim_equity")
silver.set_df(dim_equity)

# Read returns in-memory DataFrame
df = silver.read()  # Returns dim_equity
```

### Integration with BaseModel

```python
class CustomModel(BaseModel):
    def _load_bronze_table(self, table_name: str) -> DataFrame:
        """Override to use BronzeTable."""
        bronze = BronzeTable(
            self.connection.spark,
            self.storage_router,
            table_name
        )
        return bronze.read(merge_schema=True)
```

---

## Storage Configuration

**File:** `configs/storage.json`

The storage configuration defines roots and table mappings.

### Configuration Schema

```json
{
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver"
  },
  "tables": {
    "logical_table_name": {
      "rel": "provider/table_path",
      "partition": ["col1", "col2"]
    }
  }
}
```

### Example Configuration

```json
{
  "roots": {
    "bronze": "storage/bronze",
    "silver": "storage/silver",
    "equity_silver": "storage/silver/equity",
    "corporate_silver": "storage/silver/corporate"
  },
  "tables": {
    "ref_all_tickers": {
      "rel": "polygon/ref_all_tickers",
      "partition": []
    },
    "prices_daily": {
      "rel": "polygon/prices_daily",
      "partition": ["ticker"]
    },
    "prices_daily_grouped": {
      "rel": "polygon/prices_daily_grouped",
      "partition": ["ticker"]
    }
  }
}
```

---

## Benefits

### StorageRouter

- **Centralized path logic**: Single source of truth for paths
- **Configuration-driven**: Easy to change storage locations
- **Backend agnostic**: Works with any file system
- **Immutable**: Thread-safe, prevents accidental modification

### BronzeTable

- **Schema merging**: Handles API schema evolution
- **Simple API**: One method to read Bronze data
- **Error prevention**: Avoids schema mismatch errors

### SilverPath

- **Flexible**: Supports both Parquet and in-memory
- **Override capability**: Easy testing and prototyping
- **Consistent interface**: Same API for all Silver tables

---

## Best Practices

1. **Use StorageRouter**: Never hardcode paths
2. **Enable schema merging**: For Bronze tables from evolving APIs
3. **Use logical names**: Abstract from physical storage
4. **Test with overrides**: Use `set_df()` for unit tests
5. **Partition strategically**: Balance query performance vs file count

---

## Related Documentation

- [BaseModel](base-model.md) - Uses StorageRouter for path management
- [Connection System](connection-system.md) - Reads Parquet files via connections
- [UniversalSession](universal-session.md) - High-level data access
