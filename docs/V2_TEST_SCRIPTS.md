# v2.0 Test Scripts Guide

**Last Updated**: 2025-11-21
**Status**: All scripts working ✓

This document provides usage examples and expected results for all v2.0 test scripts.

---

## Overview

The test scripts in `scripts/test/` validate the v2.0 architecture, including:
- ✅ Backend-agnostic schema aliases
- ✅ DuckDB view auto-initialization
- ✅ Inherited base measure execution
- ✅ Model instantiation and configuration loading

---

## Test Scripts

### 1. Table Explorer (`explore_tables.py`)

**Purpose**: Browse DuckDB tables and show sample data.

**Usage**:
```bash
# Show top 10 rows from all tables
python -m scripts.test.explore_tables

# Show top 5 rows
python -m scripts.test.explore_tables --limit 5

# Filter to specific schema
python -m scripts.test.explore_tables --schema stocks

# Custom database path
python -m scripts.test.explore_tables --db-path /path/to/custom.db
```

**Expected Output**:
```
================================================================================
DUCKDB TABLE EXPLORER
================================================================================
Database: /home/user/de_Funk/storage/duckdb/analytics.db
Rows per table: 10

✓ Connected successfully

Found 3 table(s)

================================================================================
TABLE: stocks.dim_stock (VIEW)
================================================================================
Total rows: 386

Columns (12):
  - ticker: VARCHAR
  - security_name: VARCHAR
  - asset_type: VARCHAR
  ...

Sample data (first 10 rows):
ticker  security_name  asset_type  ...
A       Agilent Technologies Inc  stocks  ...
AA      Alcoa Corp                stocks  ...
...
```

**What It Shows**:
- All schemas and tables/views in the database
- Row counts for each table
- Column metadata (name, type)
- Sample data preview

---

### 2. Auto-Initialization Test (`test_duckdb_auto_init.py`)

**Purpose**: Validate DuckDB view auto-initialization behavior.

**Usage**:
```bash
python -m scripts.test.test_duckdb_auto_init
```

**Expected Output**:
```
================================================================================
Testing DuckDB View Auto-Initialization
================================================================================

[Test 1] In-memory database (should skip)
--------------------------------------------------------------------------------
✓ In-memory connection created (no view initialization expected)

[Test 2] Persistent database (should auto-initialize)
--------------------------------------------------------------------------------
Creating connection to: /tmp/tmp.../test.db
✓ Found 4 v2.0 model schemas:
  - core
  - company
  - stocks
  - options

[Test 3] Second connection (should skip re-initialization)
--------------------------------------------------------------------------------
✓ Second connection created (should have detected existing views)

[Test 4] Auto-init disabled (should skip)
--------------------------------------------------------------------------------
✓ No schemas created (auto_init_views=False)

================================================================================
✓ All tests passed!
================================================================================

Behavior Summary:
- ✓ In-memory databases skip initialization (fast for tests)
- ✓ Persistent databases auto-initialize on first connection
- ✓ Subsequent connections detect existing views and skip
- ✓ auto_init_views parameter allows disabling if needed
```

**What It Tests**:
- In-memory databases skip initialization (performance)
- Persistent databases auto-create views on first connection
- Subsequent connections detect existing views and skip
- `auto_init_views=False` parameter disables initialization

---

### 3. Base Measure Test (`test_base_measure.py`)

**Purpose**: Test inherited base measures from `_base.securities`.

**Usage**:
```bash
python -m scripts.test.test_base_measure
```

**Expected Output**:
```
================================================================================
Testing Base Inherited Measure: avg_close_price
================================================================================

✓ Registry created
  Available models: ['company', 'options', 'stocks', ...]

✓ Loaded stocks config

✓ Found inherited measure: avg_close_price
  Source: fact_prices.close

[Attempting to load model instance...]

✓ Model instantiated
  Model name: stocks
  Backend: duckdb

[Attempting to calculate avg_close_price...]

✓ SUCCESS! Measure calculated
  Result type: <class 'models.base.backend.adapter.QueryResult'>
  Result shape: (1, 1)

Preview:
   measure_value
0      39.319281
```

**What It Tests**:
- ModelRegistry loads v2.0 modular configs
- Inherited measures are present in loaded config
- StocksModel instantiates successfully
- Inherited `avg_close_price` measure executes
- Results are returned correctly

---

### 4. Debug Measure Execution (`debug_measure_execution.py`)

**Purpose**: Comprehensive debugging of measure execution flow.

**Usage**:
```bash
python -m scripts.test.debug_measure_execution
```

**Expected Output** (abbreviated):
```
================================================================================
DEBUG: Inherited Measure Execution Flow
================================================================================

[1] LOADING CONFIGURATION
--------------------------------------------------------------------------------
✓ Loaded stocks model config

[2] CHECKING INHERITED MEASURES
--------------------------------------------------------------------------------
✓ Found inherited measure: avg_close_price
  Source: fact_prices.close
  Aggregation: avg
  Description: Average closing price

[3] CHECKING SCHEMA FOR TABLE PATHS
--------------------------------------------------------------------------------
✓ Found table definition: fact_prices
  Keys: ['description', 'columns', 'primary_key', 'partitions', 'tags', 'is_alias', 'alias_for', 'path']
  Path: facts/fact_stock_prices

✓ Found table definition: fact_stock_prices
  Keys: ['description', 'columns', 'primary_key', 'partitions', 'tags']
  ⚠ NO 'path' KEY - this will cause _resolve_table_path to fail!

[4] CHECKING GRAPH FOR TABLE DEFINITIONS
--------------------------------------------------------------------------------
Available graph nodes: ['_dim_security_base', '_fact_prices_base', 'dim_stock', 'fact_stock_prices', 'fact_stock_technicals']

✓ Found graph node: fact_stock_prices
  Keys: ['from', 'filters', 'select', 'tags']
  Filters: ["asset_type = 'stocks'", 'trade_date IS NOT NULL', 'ticker IS NOT NULL']

[5] ATTEMPTING TO INSTANTIATE MODEL
--------------------------------------------------------------------------------
✓ Model instantiated successfully
  Model name: stocks
  Backend: duckdb

[7] TESTING TABLE REFERENCE RESOLUTION
--------------------------------------------------------------------------------
Attempting to resolve: fact_prices
  ✓ Resolved to: read_parquet('storage/silver/stocks/facts/fact_stock_prices')

Attempting to resolve: fact_stock_prices
  ✓ Resolved to: read_parquet('storage/silver/stocks/facts/fact_stock_prices')

[9] TESTING MEASURE EXECUTION
--------------------------------------------------------------------------------
Attempting to calculate inherited measure: avg_close_price
  ✓ Measure executed successfully!
  Result type: <class 'models.base.backend.adapter.QueryResult'>
  Result data shape: (1, 1)

[10] FILTER ENGINE INVESTIGATION
--------------------------------------------------------------------------------
✓ FilterEngine exists in core.session.filters
  Purpose: Runtime filter application (query-time)
  Methods: apply_filters(), apply_from_session()
  Used by: UniversalSession, BaseModel query methods

[11] BUILD-TIME FILTER INVESTIGATION
--------------------------------------------------------------------------------
✗ BaseModel._apply_filters() NOT found

================================================================================
DEBUG COMPLETE
================================================================================
```

**What It Traces**:
1. Configuration loading via ModelConfigLoader
2. Inherited measure discovery in merged config
3. Schema table path checking (aliased vs real tables)
4. Graph node definitions and filters
5. Model instantiation
6. Model build state
7. Table reference resolution (adapter layer)
8. DuckDB view checking
9. Measure execution attempt
10. FilterEngine investigation
11. Build-time filter investigation

**Use When**:
- Debugging measure execution failures
- Understanding the inheritance flow
- Investigating table resolution issues
- Tracing filter application

---

## Quick Test Sequence

To validate your v2.0 setup, run in this order:

```bash
# 1. Check DuckDB views exist and show data
python -m scripts.test.explore_tables --schema stocks

# 2. Test auto-initialization behavior
python -m scripts.test.test_duckdb_auto_init

# 3. Test inherited measure execution
python -m scripts.test.test_base_measure

# 4. Full diagnostic if issues arise
python -m scripts.test.debug_measure_execution
```

---

## Recent Fixes (2025-11-21)

### Parameter Name Correction

**Issue**: Test scripts were using `database=":memory:"` parameter, but `DuckDBConnection` expects `db_path=":memory:"`.

**Fixed Scripts**:
- `test_duckdb_auto_init.py`
- `debug_measure_execution.py`

**Error Before Fix**:
```
TypeError: DuckDBConnection.__init__() got an unexpected keyword argument 'database'
```

**Solution**:
```python
# Before (incorrect)
conn = DuckDBConnection(database=":memory:")

# After (correct)
conn = DuckDBConnection(db_path=":memory:")
```

### Defensive Cleanup

**Issue**: `AttributeError: 'DuckDBConnection' object has no attribute '_cached_tables'` in `__del__` when initialization failed.

**Root Cause**: If `__init__()` throws an exception before setting `_cached_tables`, the `__del__()` method would fail trying to clean up.

**Solution**: Made `stop()` and `__del__()` defensive:

```python
def stop(self):
    """Close the DuckDB connection."""
    # Clear cached tables (only if initialized)
    if hasattr(self, '_cached_tables') and hasattr(self, 'conn') and self.conn:
        for name in list(self._cached_tables.keys()):
            self.conn.execute(f"DROP TABLE IF EXISTS {name}")
        self._cached_tables.clear()

    # Close connection
    if hasattr(self, 'conn') and self.conn:
        self.conn.close()
        self.conn = None

def __del__(self):
    """Cleanup on deletion."""
    try:
        self.stop()
    except Exception:
        # Silently handle cleanup errors (object may be partially initialized)
        pass
```

---

## Test Results Summary

| Test Script | Status | Purpose |
|-------------|--------|---------|
| `explore_tables.py` | ✅ PASS | Browse DuckDB tables and data |
| `test_duckdb_auto_init.py` | ✅ PASS | Validate view auto-initialization |
| `test_base_measure.py` | ✅ PASS | Test inherited measure execution |
| `debug_measure_execution.py` | ✅ PASS | Full diagnostic tracing |

All scripts successfully validate the v2.0 architecture:
- ✅ Backend-agnostic schema aliases work
- ✅ DuckDB views auto-initialize correctly
- ✅ Inherited measures execute properly
- ✅ Model loading and instantiation functional

---

## Troubleshooting

### No tables found in database

**Error**:
```
⚠ No tables found in database
Run setup script first: python -m scripts.setup.setup_duckdb_views
```

**Solution**: Build silver layer first:
```bash
# Build all v2.0 models
python -m scripts.build.build_silver_layer --model core
python -m scripts.build.build_silver_layer --model company
python -m scripts.build.build_silver_layer --model stocks

# Views will auto-initialize on next connection
python -m scripts.test.explore_tables
```

### Table not found errors in measures

**Error**:
```
ValueError: Table 'fact_prices' not found in model 'stocks' schema
```

**Solution**: This should not occur with v2.0 architecture. If it does:
1. Check schema aliases in config: `python -m scripts.test.debug_measure_execution`
2. Verify `ModelConfigLoader._add_schema_aliases()` is working
3. Check `config/model_loader.py` for inheritance resolution

### Connection parameter errors

**Error**:
```
TypeError: DuckDBConnection.__init__() got an unexpected keyword argument 'database'
```

**Solution**: Use `db_path=` parameter instead:
```python
# Correct
conn = DuckDBConnection(db_path=":memory:")

# Incorrect
conn = DuckDBConnection(database=":memory:")
```

---

## See Also

- **`BACKEND_AGNOSTIC_ALIASES.md`**: Backend-agnostic aliasing architecture
- **`V2_COMPLETION_STATUS.md`**: Overall v2.0 migration status
- **`BUILD_PROCESS.md`**: How to build silver layer models
- **`ARCHITECTURE_ANALYSIS.md`**: Deep dive on v1.x vs v2.0 architecture
