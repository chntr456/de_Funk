# Proposal: Fix DuckDB Filter System Crashes

**Date**: 2025-12-07
**Status**: Draft
**Priority**: High
**Author**: Claude (AI Assistant)

## Executive Summary

Three distinct issues are causing crashes when the UI tries to load filter options from DuckDB:

1. **Missing Silver Layer** → Falls back to building ALL model tables from Bronze → **HANGS**
2. **Heavy Window Functions** → `fact_stock_prices` computes 15+ window functions over 10M rows → **HANGS**
3. **Numeric Quoting Bug** → FilterEngine incorrectly quotes numbers → DuckDB type mismatch errors

## ⚠️ ROOT CAUSE IDENTIFIED

When `session.get_table('stocks', 'dim_stock')` is called:
1. `ensure_built()` is triggered (line 263-270 in `models/base/model.py`)
2. This builds **ALL** tables in the model, not just `dim_stock`
3. `fact_stock_prices` has 15+ complex window functions (RSI, SMAs, Bollinger Bands, volatility)
4. These window functions must process the **ENTIRE** 10M row prices table
5. **Result**: Hangs for minutes or crashes due to memory/timeout

## Issue 1: Ticker List Not Loading (Primary Crash)

### Root Cause

When the UI calls `get_filter_options_from_db()`, it triggers this chain:

```
render_select_filter()
  → get_filter_options_from_db(source)
    → _storage_service.get_table('stocks', 'dim_stock')
      → UniversalSession.get_table()
        → _get_table_from_view_or_build()
          → connection.table('stocks.dim_stock')  # FAILS - view doesn't exist
          → model.get_table()  # FALLBACK - builds from Bronze
            → BaseModel.build()
              → GraphBuilder.build_node()
                → connection.read_table(bronze_path)  # READS ENTIRE BRONZE DELTA TABLE
```

### Why It Hangs/Crashes

1. **No DuckDB views exist** - The `stocks.dim_stock` view was never created
2. **Fallback to Bronze build** - Session tries to build the model on-the-fly
3. **Large Delta tables** - Bronze `securities_reference` and `securities_prices_daily` are large
4. **Multiple reads** - The logs show the same tables being read multiple times
5. **Resource exhaustion** - DuckDB/PyCharm runs out of memory or hits other limits

### Evidence from Logs

```
Building stocks.dim_stock from source (may be slow)
Auto-detected Delta table at .../bronze/securities_reference
Auto-detected Delta table at .../bronze/securities_prices_daily
Auto-detected Delta table at .../bronze/securities_reference  # AGAIN
Auto-detected Delta table at .../bronze/securities_prices_daily  # AGAIN
[HANG/CRASH]
```

### Solution

**Prerequisite Steps** (run before using UI):

```bash
# 1. Build Silver layer models (if not already done)
python -m scripts.build_silver_layer

# 2. Setup DuckDB views pointing to Silver layer
python -m scripts.setup.setup_duckdb_views --update
```

**Code Fix** (optional safety improvement):

Add a check in `get_filter_options_from_db()` to fail fast if views don't exist:

```python
# app/ui/components/dynamic_filters.py - lines 366-389

@st.cache_data(ttl=300)
def get_filter_options_from_db(source, _connection, _storage_service):
    try:
        # Check if view exists before trying (prevents expensive fallback)
        view_name = f"{source.model}.{source.table}"
        if hasattr(_connection, 'has_view'):
            if not _connection.has_view(view_name):
                st.warning(f"View {view_name} not found. Run: python -m scripts.setup.setup_duckdb_views")
                return []

        # Existing code...
        df = _storage_service.get_table(source.model, source.table, use_cache=True)
        # ...
```

## Issue 2: Numeric Quoting Bug in FilterEngine

### Root Cause

`FilterEngine._apply_duckdb_filters()` incorrectly quotes numeric values as strings.

**Location**: `core/session/filters.py` lines 209-220 and 312-323

### Evidence

```python
# Current code (BUGGY):
conditions.append(f"{col_name} >= '{value['min']}'")  # 'min' is quoted

# Generated SQL:
# volume >= '1000000'  ← WRONG - comparing number to string

# Expected:
# volume >= 1000000  ← CORRECT
```

### Validation Results

```
Test 1.1: Numeric min/max filter - ❌ BUG CONFIRMED
Test 1.4: Mixed filters - ❌ BUG CONFIRMED (volume, market_cap quoted)
Test 1.5: Comparison operators - ❌ BUG CONFIRMED (gt, lt, gte, lte quoted)
```

### Affected Code Paths

| File | Location | Impact |
|------|----------|--------|
| `models/api/session.py` | Lines 289, 308, 327, 347 | HIGH - All exhibit data retrieval |
| `models/api/auto_join.py` | Lines 305, 393 | MEDIUM - Cross-model joins |
| `app/notebook/managers/notebook_manager.py` | Line 840 | MEDIUM - Weighted aggregates |

### Solution

Fix `FilterEngine` to NOT quote numeric values:

```python
# core/session/filters.py - _apply_duckdb_filters() and build_filter_sql()

def _format_value_for_sql(value):
    """Format a value for SQL, quoting strings but not numbers."""
    if isinstance(value, (int, float)):
        return str(value)  # No quotes
    elif isinstance(value, str):
        return f"'{value}'"  # Quote strings
    else:
        return f"'{value}'"  # Default to quoted

# Then use this in conditions:
if 'min' in value:
    formatted = _format_value_for_sql(value['min'])
    conditions.append(f"{col_name} >= {formatted}")
```

### Contrast with Working Implementation

`DuckDBConnection.apply_filters()` (lines 553-556) does it correctly:

```python
# CORRECT - no quotes:
if 'min' in value and value['min'] is not None and value['min'] > 0:
    conditions.append(f"{column} >= {value['min']}")  # NO QUOTES
```

## Recommended Fix Order

### Quick Workaround (Immediate)

If you just need filter options working NOW:
```bash
python -m scripts.setup.quick_dim_stock_view
```
This creates a lightweight `stocks.dim_stock` view directly from Bronze, bypassing the heavy model build.

### Full Fix (Recommended for Production)

1. **First**: Build Silver layer using Spark (handles window functions efficiently)
   ```bash
   python -m scripts.build_silver_layer
   ```

2. **Second**: Setup DuckDB views pointing to pre-built Silver tables
   ```bash
   python -m scripts.setup.setup_duckdb_views --update
   ```

3. **Third**: Verify ticker list loads after views are created

4. **Fourth**: If numeric filter issues persist, fix the FilterEngine quoting bug

## Validation Scripts

Two diagnostic scripts have been created:

1. **`scripts/test/validate_filter_system.py`** - Tests FilterEngine SQL generation
2. **`scripts/test/diagnose_ticker_load.py`** - Isolates ticker loading crash point

Run diagnostics:
```bash
python -m scripts.test.diagnose_ticker_load
```

## Summary

| Issue | Root Cause | Fix |
|-------|------------|-----|
| Ticker list not loading | `ensure_built()` computes ALL tables including heavy window functions | Use quick_dim_stock_view.py or build Silver layer first |
| PyCharm crashing | 15+ window functions over 10M rows in DuckDB | Build Silver layer with Spark instead |
| Numeric filter errors | FilterEngine quotes numbers | Fix _format_value_for_sql() |

## Key Code Locations

| File | Line | Issue |
|------|------|-------|
| `models/base/model.py` | 263-270 | `ensure_built()` builds ALL tables |
| `configs/models/stocks/graph.yaml` | 42-70 | 15+ window functions in fact_stock_prices |
| `core/session/filters.py` | 209-220 | Numeric quoting bug |

## Files to Review

- `core/session/filters.py` - FilterEngine implementation
- `app/ui/components/dynamic_filters.py` - Filter option loading
- `models/api/session.py` - UniversalSession.get_table()
- `scripts/setup/setup_duckdb_views.py` - View creation script
