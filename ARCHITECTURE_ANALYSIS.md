# Architecture Analysis: v1.x vs v2.0 Model System

**Generated**: 2025-11-21
**Purpose**: Document how measure execution and table resolution actually works, comparing old Polygon-based v1.x with new Alpha Vantage v2.0

---

## Key Findings from Debug Investigation

### 1. Schema Path Regression (CRITICAL ISSUE)

**v1.x (Working)**:
```yaml
# configs/models/equity.yaml (old Polygon version)
schema:
  facts:
    fact_equity_prices:
      path: facts/fact_equity_prices  # ← EXPLICIT PATH
      description: "..."
      columns: {...}
```

**v2.0 (Broken)**:
```yaml
# configs/models/stocks/schema.yaml (current)
facts:
  fact_stock_prices:
    # NO 'path' KEY!
    description: "..."
    columns: {...}
```

**Impact**:
- `DuckDBAdapter.get_table_reference()` calls `_resolve_table_path()`
- `_resolve_table_path()` tries to access `schema['facts'][table_name]['path']`
- **KeyError** because 'path' key doesn't exist in v2.0 schemas!

**Root Cause**: During v2.0 modular YAML redesign, we removed `path` entries from schema.yaml files, assuming graph nodes would handle path resolution. But the adapter still expects schema paths for measure execution.

---

### 2. Filter Architecture: Build-Time vs Query-Time

**FilterEngine** (`core/session/filters.py`):
- **Purpose**: Runtime (query-time) filter application
- **Used by**: UniversalSession, BaseModel query methods, notebooks
- **Operates on**: Already-loaded DataFrames
- **Format**: Dict-based filter specs with operators

**My _apply_filters()** (added in commit 463d57a):
- **Purpose**: Build-time filter application in `_build_nodes()`
- **Operates on**: DataFrames during model.build()
- **Format**: SQL WHERE clause strings (e.g., `"asset_type = 'stocks'"`)

**Question**: Are these redundant or complementary?

**Answer**: They serve DIFFERENT purposes:
- **Build-time filters** (my addition): Filter data BEFORE writing to Silver layer
  - Example: `asset_type = 'stocks'` to separate stocks from options in unified bronze
  - Result: Silver Parquet files contain only filtered data

- **Query-time filters** (FilterEngine): Filter data DURING queries
  - Example: `ticker = 'AAPL'` to get specific stock data
  - Result: Dynamic filtering without rebuilding Silver layer

**But**: Build-time filters may have ALREADY been working through a different mechanism I haven't found yet.

---

### 3. How Measures Actually Resolve Tables

**Current Flow** (as designed):
```
1. measure.to_sql(adapter)
2. adapter.get_table_reference(table_name)  # "fact_prices"
3. adapter._resolve_table_path(table_name)
4. Look up: schema['facts'][table_name]['path']
5. Return: f"read_parquet('{path}/*.parquet')"
```

**Problem**: Step 4 fails because v2.0 schemas don't have 'path' keys!

**Proposed Solutions**:

**Option A: Restore schema paths** (matches v1.x pattern)
```yaml
# stocks/schema.yaml
facts:
  fact_stock_prices:
    path: facts/fact_stock_prices  # Add this back
    description: "..."
```

**Option B: Use DuckDB views** (current approach with alias views)
```sql
-- setup_duckdb_views.py creates:
CREATE VIEW stocks.fact_stock_prices AS
  SELECT * FROM read_parquet('storage/silver/stocks/facts/fact_stock_prices/*.parquet');

CREATE VIEW stocks.fact_prices AS  -- Alias for base measures
  SELECT * FROM stocks.fact_stock_prices;
```

Then queries just reference `stocks.fact_prices` directly (no path resolution needed).

**Option C: Hybrid approach**
- Schema has paths for adapter resolution
- DuckDB views for performance and aliasing
- Both work together

---

### 4. The Missing Piece: How Were v2.0 Models Working At All?

**Hypothesis**: v2.0 models with measures were only tested AFTER running `setup_duckdb_views.py`.

**Evidence**:
- `setup_duckdb_views.py` creates persistent views in DuckDB database
- Queries that reference view names (e.g., `stocks.fact_stock_prices`) work via DuckDB
- But this BYPASSES the adapter's path resolution entirely
- Measures that use adapter.get_table_reference() would FAIL without views

**Test**: What happens if we try to use a measure without DuckDB views set up?
- Answer: Should get "Table not found in model schema" error from _resolve_table_path()

---

### 5. Graph Filters Investigation

**Graph YAML** (stocks/graph.yaml):
```yaml
nodes:
  fact_stock_prices:
    from: bronze.securities_prices_daily
    filters:
      - "asset_type = 'stocks'"      # ← Filters ARE defined!
      - "trade_date IS NOT NULL"
      - "ticker IS NOT NULL"
```

**Question**: Were these filters being applied before my `_apply_filters()` addition?

**Check git history**:
```bash
git show 9518e1b:models/base/model.py | grep -A 30 "for node_id, node_config"
```

**Result**: NO filter application code before my commit!
- Only `select` and `derive` were applied
- `filters` in YAML were ignored during build

**BUT**: This doesn't mean filters weren't working. They could have been:
1. Applied at ingestion time (Bronze layer creation)
2. Applied via SQL views
3. Never actually used (data was pre-filtered another way)

---

## Recommendations

### Immediate Actions

1. **Add schema paths back** (Option A + C)
   - Update ModelConfigLoader to auto-populate `path` entries
   - Based on model storage root + table name convention
   - Enables adapter path resolution to work

2. **Keep my filter implementation** (with caveat)
   - Build-time filters ARE useful for unified bronze tables
   - But verify they weren't already working another way
   - Add tests to confirm filtering is actually happening

3. **Keep alias views** (Option B + C)
   - Alias views enable base measure inheritance without modification
   - Performance benefit (persistent views vs file scanning)
   - Namespace isolation (stocks.fact_prices vs options.fact_prices)

### Investigation Needed

1. **How were v2.0 models built before?**
   - Check if there's data in storage/silver/stocks/
   - If yes, how was it created without filter support?
   - Look for alternative build scripts

2. **Test measure execution without DuckDB views**
   - Delete analytics.db
   - Try to calculate a measure
   - See exact error to confirm path resolution issue

3. **Check UniversalSession flow**
   - Does it use adapter.get_table_reference()?
   - Or does it query DuckDB views directly?
   - This explains which path is actually taken

---

## Code Audit Results

### Files Modified by Me (Last 3 Commits)

1. **models/base/model.py** - Added `_apply_filters()` method
2. **scripts/setup/setup_duckdb_views.py** - Added alias views
3. **configs/notebooks/stocks/stock_analysis_v2.md** - Fixed missing 'id'
4. **configs/models/options/graph.yaml** - Removed cross-file node extends

### Potential Issues

**Issue 1: Duplicate filter logic**
- FilterEngine (query-time) vs _apply_filters (build-time)
- Could be confusing which applies when
- **Fix**: Document clearly in CLAUDE.md

**Issue 2: Schema path missing**
- v2.0 schemas lack 'path' entries
- Breaks adapter table resolution
- **Fix**: Auto-populate paths in ModelConfigLoader

**Issue 3: Unclear if build filters working**
- No evidence filters were applied before my commit
- But also no evidence they were needed
- **Fix**: Test with actual data to confirm

---

## Next Steps

1. Run test script to completion (fix DuckDB connection init)
2. Test measure execution with and without views
3. Check if Silver layer exists and how it was created
4. Review git history for alternative build methods
5. Make informed decision on keeping/removing my changes

---

## Questions for User

1. **Were v2.0 models ever successfully built and used before my changes?**
2. **Do you have data in storage/silver/stocks/ currently?**
3. **Can you try running a measure and share the exact error?**
4. **Should I revert my filter changes and investigate the old approach?**
