# Streamlit App Refactoring Plan
## Migrating to Unified Measure Framework

**Created:** 2025-11-12
**Purpose:** Document changes needed in Streamlit app to integrate with the new unified measure framework

---

## Executive Summary

The Streamlit app currently uses an **old approach** for calculating and displaying weighted aggregates:
1. A script (`build_weighted_aggregates_duckdb.py`) materializes views in the silver layer
2. `NotebookSession._get_weighted_aggregate_data()` queries these views directly
3. Two versions of the weighted_aggregate_chart component exist (old and new)

**The new unified measure framework eliminates the need for:**
- Materialized views in silver layer
- Build scripts to pre-calculate aggregates
- Business logic in UI layer
- Backend-specific code duplication

**Impact:** This is the **biggest backend change** affecting the Streamlit app.

---

## Current Architecture Analysis

### File Inventory

| File | Status | Purpose | Issues |
|------|--------|---------|--------|
| `app/ui/components/exhibits/weighted_aggregate_chart.py` | **OLD** | Calculates weighted aggregates in Python/NumPy (lines 26-156) | Business logic in UI layer |
| `app/ui/components/exhibits/weighted_aggregate_chart_model.py` | **NEW** | Pure renderer expecting pre-calculated data | ✓ Good separation of concerns |
| `app/notebook/api/notebook_session.py` | **NEEDS UPDATE** | Queries materialized views instead of using measure framework | Should call `model.calculate_measure()` |
| `app/ui/components/exhibits/__init__.py` | **NEEDS UPDATE** | Imports OLD weighted_aggregate_chart | Should import new version |
| `app/ui/components/notebook_view.py` | ✓ **CORRECT** | Imports NEW weighted_aggregate_chart_model | Already using new version |
| `app/ui/components/markdown_renderer.py` | ✓ **CORRECT** | Imports NEW weighted_aggregate_chart_model | Already using new version |

### Data Flow - Current vs. Desired

**CURRENT FLOW (Materialized Views):**
```
1. User runs: build_weighted_aggregates_duckdb.py
   ↓
2. Script creates materialized views: equal_weighted_index, volume_weighted_index, etc.
   ↓
3. NotebookSession._get_weighted_aggregate_data() queries views directly:
   SELECT * FROM equal_weighted_index WHERE ...
   ↓
4. weighted_aggregate_chart_model.py renders pre-calculated data
```

**DESIRED FLOW (Unified Measure Framework):**
```
1. Exhibit config references measure names: ["avg_close_price", "volume_weighted_index"]
   ↓
2. NotebookSession._get_weighted_aggregate_data() calls model.calculate_measure():
   model.calculate_measure('volume_weighted_index')
   ↓
3. MeasureExecutor generates SQL via backend adapter
   ↓
4. weighted_aggregate_chart_model.py renders results
```

**Benefits:**
- ✅ No build script needed
- ✅ Real-time calculations
- ✅ Works with both DuckDB and Spark
- ✅ Consistent with rest of framework
- ✅ Easier to add new measures (just update YAML)

---

## Code Analysis

### 1. NotebookSession._get_weighted_aggregate_data()

**Location:** `app/notebook/api/notebook_session.py:345-448`

**Current Implementation:**
```python
def _get_weighted_aggregate_data(self, exhibit: Exhibit) -> Any:
    """
    Get data for weighted aggregate charts by querying model-defined measures.

    This queries pre-built weighted aggregate views from the silver layer,
    avoiding the need for UI-level calculations.
    """
    # ... filter building ...

    # Query each weighted aggregate measure with dynamic normalization
    results = []
    for measure_id in measure_ids:
        # PROBLEM: Queries materialized view directly
        sql = f"""
        WITH raw_data AS (
            SELECT
                {aggregate_by},
                weighted_value
            FROM {measure_id}  -- <-- Direct view query!
            WHERE {where_clause}
            ORDER BY {aggregate_by}
        ),
        base_value AS (
            SELECT
                weighted_value as base_weighted_value
            FROM raw_data
            LIMIT 1
        )
        SELECT
            rd.{aggregate_by},
            (rd.weighted_value / bv.base_weighted_value) * 100 as weighted_value,
            '{measure_id}' as measure_id
        FROM raw_data rd
        CROSS JOIN base_value bv
        ORDER BY rd.{aggregate_by}
        """

        df = self.connection.conn.execute(sql).fetchdf()
        results.append(df)
```

**Issues:**
1. ❌ Queries materialized views instead of using measure framework
2. ❌ Requires running `build_weighted_aggregates_duckdb.py` first
3. ❌ Only works with DuckDB (no Spark support)
4. ❌ Manual SQL construction (should use measure framework)
5. ❌ Normalization logic duplicated (should be in measure config)

**Proposed Refactoring:**
```python
def _get_weighted_aggregate_data(self, exhibit: Exhibit) -> Any:
    """
    Get data for weighted aggregate charts using unified measure framework.

    Calculates measures on-demand using the model's measure executor.
    Works with both DuckDB and Spark backends.
    """
    if not hasattr(exhibit, 'value_measures') or not exhibit.value_measures:
        raise ValueError(f"Weighted aggregate exhibit {exhibit.id} has no value_measures defined")

    # Get model from session
    model_name = self._parse_source(exhibit.source)[0] if hasattr(exhibit, 'source') else 'company'
    model = self.get_model_session(model_name)

    if not model:
        raise ValueError(f"Model '{model_name}' not available. Check model initialization.")

    # Build filters
    filters = self._build_filters(exhibit)

    # Calculate each measure using unified framework
    results = []
    for measure_name in exhibit.value_measures:
        try:
            # Use unified measure framework!
            result = model.calculate_measure(
                measure_name,
                filters=filters,
                # Additional kwargs can be passed from exhibit config
            )

            # Convert to pandas for processing
            measure_df = result.data

            # Add measure_id column for chart rendering
            measure_df['measure_id'] = measure_name

            # Optional: Apply normalization if configured
            if hasattr(exhibit, 'normalize') and exhibit.normalize:
                aggregate_by = exhibit.aggregate_by or 'trade_date'
                base_value = measure_df.iloc[0]['measure_value'] if len(measure_df) > 0 else 1
                measure_df['weighted_value'] = (measure_df['measure_value'] / base_value) * 100
            else:
                # Rename measure_value to weighted_value for chart compatibility
                measure_df['weighted_value'] = measure_df['measure_value']

            results.append(measure_df)

        except ValueError as e:
            raise ValueError(
                f"Error calculating measure '{measure_name}': {str(e)}. "
                f"Check that measure is defined in {model_name}.yaml"
            )

    # Combine all measures
    if results:
        combined_df = pd.concat(results, ignore_index=True)
        # Convert to DuckDB relation for consistency with other exhibit types
        return self.connection.conn.from_df(combined_df)
    else:
        # Return empty DataFrame with expected schema
        aggregate_by = exhibit.aggregate_by or 'trade_date'
        return self.connection.conn.from_df(
            pd.DataFrame(columns=[aggregate_by, 'weighted_value', 'measure_id'])
        )
```

**Key Changes:**
1. ✅ Uses `model.calculate_measure()` instead of querying views
2. ✅ Works with both DuckDB and Spark (backend abstraction)
3. ✅ No dependency on build scripts
4. ✅ Leverages all measure framework features (filters, etc.)
5. ✅ Normalization is optional and configurable per exhibit

---

### 2. weighted_aggregate_chart.py (OLD VERSION)

**Location:** `app/ui/components/exhibits/weighted_aggregate_chart.py`

**Status:** ❌ **Should be removed or archived**

**Current Usage:**
- Imported by `app/ui/components/exhibits/__init__.py` (line 11)
- Contains Python/NumPy calculation logic (lines 26-156)

**Issues:**
1. ❌ Business logic in UI layer (violates separation of concerns)
2. ❌ Duplicates weighting strategies now in `models/domains/equities/weighting.py`
3. ❌ Only works with DuckDB
4. ❌ Calculates on-the-fly instead of using optimized SQL

**Action Required:**
```python
# app/ui/components/exhibits/__init__.py

# BEFORE:
from .weighted_aggregate_chart import render_weighted_aggregate_chart

# AFTER:
from .weighted_aggregate_chart_model import render_weighted_aggregate_chart

# OR (if you want to keep both temporarily for backward compatibility):
# from .weighted_aggregate_chart_model import render_weighted_aggregate_chart
# from .weighted_aggregate_chart import render_weighted_aggregate_chart as render_weighted_aggregate_chart_legacy
```

**Recommendation:**
- Archive `weighted_aggregate_chart.py` to `docs/archive/experimental/`
- Update `__init__.py` to import from `weighted_aggregate_chart_model.py`
- Add deprecation warning if the old version is still referenced anywhere

---

### 3. weighted_aggregate_chart_model.py (NEW VERSION)

**Location:** `app/ui/components/exhibits/weighted_aggregate_chart_model.py`

**Status:** ✅ **Already correct - pure renderer**

**Current Implementation:** Perfect! This is a clean separation of concerns:
```python
def render_weighted_aggregate_chart(exhibit, pdf: pd.DataFrame):
    """
    Render weighted aggregate chart with model-calculated data.

    The data comes pre-calculated from weighted aggregate views in the silver layer.
    This component only handles rendering - no calculation logic.

    Args:
        exhibit: Exhibit configuration
        pdf: Pandas DataFrame with columns:
            - aggregate_by (e.g., 'trade_date'): Grouping dimension
            - weighted_value: Pre-calculated weighted aggregate value
            - measure_id: Identifier for the weighting method
    """
    # Pure rendering logic only
    # ✓ No business logic
    # ✓ No calculations
    # ✓ Just visualization
```

**No changes needed** - this is already the correct pattern!

---

## Migration Steps

### Phase 1: Update NotebookSession (Backend Integration)

**Priority:** 🔴 **CRITICAL** - This is the core backend change

1. **Update `_get_weighted_aggregate_data()` method**
   - Location: `app/notebook/api/notebook_session.py:345-448`
   - Replace view queries with `model.calculate_measure()` calls
   - See proposed implementation above

2. **Add model session retrieval**
   - Ensure `get_model_session()` returns initialized models with measure executors
   - Verify model registry is properly loaded

3. **Update filter handling**
   - Ensure filters are passed to `calculate_measure()` in correct format
   - Test date range filters, ticker filters, etc.

**Testing:**
```python
# Test that measures can be calculated on-demand
from app.notebook.api.notebook_session import NotebookSession
from core.context import RepoContext

ctx = RepoContext.from_repo_root(connection_type='duckdb')
session = NotebookSession(ctx.connection, ctx.storage, ctx.repo)

# Load notebook
session.load_notebook('stock_analysis.yaml')

# Get weighted aggregate data (should use measure framework)
exhibit = session._find_exhibit('weighted_index_chart')
df = session._get_weighted_aggregate_data(exhibit)

# Verify columns: trade_date, weighted_value, measure_id
assert 'weighted_value' in df.columns
assert 'measure_id' in df.columns
```

---

### Phase 2: Clean Up Import Paths

**Priority:** 🟡 **HIGH** - Ensure correct component is used

1. **Update `app/ui/components/exhibits/__init__.py`**
   ```python
   # Change from:
   from .weighted_aggregate_chart import render_weighted_aggregate_chart

   # To:
   from .weighted_aggregate_chart_model import render_weighted_aggregate_chart
   ```

2. **Archive old component**
   ```bash
   mv app/ui/components/exhibits/weighted_aggregate_chart.py \
      docs/archive/experimental/weighted_aggregate_chart_legacy.py
   ```

3. **Search for any remaining references**
   ```bash
   grep -r "from.*weighted_aggregate_chart import" app/
   grep -r "render_weighted_aggregate_chart" app/
   ```

**Verification:**
- Run Streamlit app: `streamlit run app/main.py`
- Navigate to page with weighted aggregate chart
- Verify chart renders without errors
- Check browser console for any import errors

---

### Phase 3: Update Exhibit Configurations

**Priority:** 🟡 **HIGH** - Ensure exhibits reference correct measures

**Current format (queries materialized views):**
```yaml
exhibits:
  - id: weighted_index_chart
    type: weighted_aggregate_chart
    title: "Market Indices (Multiple Weighting Methods)"
    source: company.fact_prices
    value_measures:
      - equal_weighted_index           # View name
      - volume_weighted_index          # View name
      - market_cap_weighted_index      # View name
    aggregate_by: trade_date
```

**New format (references model measures):**
```yaml
exhibits:
  - id: weighted_index_chart
    type: weighted_aggregate_chart
    title: "Market Indices (Multiple Weighting Methods)"
    source: company.fact_prices       # Model.table for context
    value_measures:
      - equal_weighted_index          # Measure name (from company.yaml)
      - volume_weighted_index         # Measure name
      - market_cap_weighted_index     # Measure name
    aggregate_by: trade_date
    normalize: true                   # Optional: normalize to base 100
```

**Notes:**
- Measure names stay the same (they match between views and YAML measures)
- But now they reference entries in `configs/models/company.yaml` measures section
- No behavior change from user perspective

**Action Items:**
1. Audit all notebook YAML files for weighted_aggregate_chart exhibits
2. Verify measure names exist in corresponding model YAML
3. Add any missing measures to model YAML if needed

---

### Phase 4: Remove Build Script Dependency

**Priority:** 🟢 **MEDIUM** - Clean up technical debt

Once the measure framework integration is working:

1. **Mark script as deprecated**
   ```python
   # scripts/build_weighted_aggregates_duckdb.py

   # Add deprecation warning at top:
   import warnings
   warnings.warn(
       "This script is deprecated. Weighted aggregates are now calculated on-demand "
       "using the unified measure framework. See docs/STREAMLIT_REFACTORING_PLAN.md",
       DeprecationWarning,
       stacklevel=2
   )
   ```

2. **Update documentation**
   - Remove references to running build script from setup docs
   - Update README to reflect on-demand calculation

3. **Eventually remove materialized views** (after migration is stable)
   - Views can be deleted from silver layer
   - This frees up storage space
   - Views are automatically kept up-to-date by measure framework

---

## Testing Strategy

### Unit Tests

**Test `_get_weighted_aggregate_data()` refactored method:**

```python
# tests/unit/test_notebook_session_measures.py

def test_get_weighted_aggregate_data_uses_measure_framework(mock_model):
    """Test that weighted aggregate data uses measure framework instead of views."""
    from app.notebook.api.notebook_session import NotebookSession
    from app.notebook.schema import Exhibit, ExhibitType

    # Create mock exhibit
    exhibit = Exhibit(
        id='test_weighted',
        type=ExhibitType.WEIGHTED_AGGREGATE_CHART,
        title='Test',
        source='company.fact_prices',
        value_measures=['volume_weighted_index'],
        aggregate_by='trade_date'
    )

    # Create session with mock model
    session = NotebookSession(mock_connection, mock_storage, mock_repo)
    session.model_sessions['company'] = {'model': mock_model, 'initialized': True}

    # Get data
    result = session._get_weighted_aggregate_data(exhibit)

    # Verify model.calculate_measure was called
    assert mock_model.calculate_measure.called
    assert mock_model.calculate_measure.call_args[0][0] == 'volume_weighted_index'

    # Verify result structure
    pdf = result.df()  # DuckDB relation to pandas
    assert 'trade_date' in pdf.columns
    assert 'weighted_value' in pdf.columns
    assert 'measure_id' in pdf.columns
```

### Integration Tests

**Test end-to-end exhibit rendering:**

```python
# tests/integration/test_streamlit_exhibits.py

def test_weighted_aggregate_chart_end_to_end(temp_dir):
    """Test weighted aggregate chart from config to rendering."""
    from core.context import RepoContext
    from app.notebook.api.notebook_session import NotebookSession

    # Initialize with real data
    ctx = RepoContext.from_repo_root(connection_type='duckdb')
    session = NotebookSession(ctx.connection, ctx.storage, ctx.repo)

    # Load notebook
    session.load_notebook('notebooks/stock_analysis.yaml')

    # Get weighted aggregate exhibit
    exhibit_id = 'weighted_index_chart'
    df = session.get_exhibit_data(exhibit_id)
    pdf = ctx.connection.to_pandas(df)

    # Verify structure
    assert len(pdf) > 0
    assert 'trade_date' in pdf.columns
    assert 'weighted_value' in pdf.columns
    assert 'measure_id' in pdf.columns

    # Verify measures
    measures = pdf['measure_id'].unique()
    assert 'equal_weighted_index' in measures
    assert 'volume_weighted_index' in measures

    # Test rendering (no errors)
    from app.ui.components.exhibits.weighted_aggregate_chart_model import render_weighted_aggregate_chart

    mock_exhibit = type('Exhibit', (), {
        'id': exhibit_id,
        'title': 'Test',
        'description': None,
        'aggregate_by': 'trade_date'
    })()

    # This should not raise
    render_weighted_aggregate_chart(mock_exhibit, pdf)
```

### Manual Testing Checklist

- [ ] Start Streamlit app: `streamlit run app/main.py`
- [ ] Navigate to notebook with weighted aggregate chart
- [ ] Verify chart loads without errors
- [ ] Test filtering (date range, tickers)
- [ ] Verify multiple weighting methods display correctly
- [ ] Test toggling measures via legend
- [ ] Check normalization (base 100)
- [ ] Verify performance (should be fast, <1s)
- [ ] Test with empty/filtered data
- [ ] Test error handling (invalid measure name)

---

## Backward Compatibility

### Option 1: Hard Cutover (Recommended)

**Pros:**
- Clean break from old approach
- Forces migration to new framework
- Removes technical debt immediately

**Cons:**
- May break existing notebooks if not updated
- Requires coordination

**Implementation:**
1. Update `_get_weighted_aggregate_data()` to use measure framework
2. Archive `weighted_aggregate_chart.py`
3. Update all exhibit configs
4. Deprecate build script

**Timeline:** 1-2 days

---

### Option 2: Gradual Migration

**Pros:**
- Zero downtime
- Can test new approach in parallel
- Easy rollback if issues

**Cons:**
- More complex
- Temporary code duplication
- Longer migration period

**Implementation:**
1. Add feature flag: `use_measure_framework = True`
2. Keep both code paths temporarily:
   ```python
   def _get_weighted_aggregate_data(self, exhibit):
       if os.getenv('USE_MEASURE_FRAMEWORK', 'true').lower() == 'true':
           return self._get_weighted_aggregate_data_v2(exhibit)  # New
       else:
           return self._get_weighted_aggregate_data_v1(exhibit)  # Old
   ```
3. Migrate notebooks one by one
4. Remove old code path after all notebooks migrated

**Timeline:** 1-2 weeks

---

## Recommended Approach

**Use Option 1 (Hard Cutover)** because:

1. ✅ New measure framework is already tested and working
2. ✅ Minimal number of files affected (mainly `notebook_session.py`)
3. ✅ Cleaner code, less maintenance
4. ✅ Consistent with rest of framework
5. ✅ Build script was already causing friction (manual step)

**Migration can be done in a single session:**
- Update `_get_weighted_aggregate_data()` (1 hour)
- Update `__init__.py` imports (5 minutes)
- Test with existing notebooks (30 minutes)
- Archive old component (5 minutes)

**Total estimated time:** ~2 hours

---

## Impact Assessment

### Files to Change

| File | Lines Changed | Type | Risk |
|------|---------------|------|------|
| `app/notebook/api/notebook_session.py` | ~50-100 | Refactor | 🟡 Medium |
| `app/ui/components/exhibits/__init__.py` | 1 | Import | 🟢 Low |
| `docs/` (documentation updates) | Various | Docs | 🟢 Low |

**Total:** 3 files, ~50-100 LOC

### Deployment Checklist

- [ ] Run all existing tests: `pytest tests/`
- [ ] Run pipeline tester: `python tests/pipeline_tester.py`
- [ ] Test all example notebooks: `python examples/measure_framework/01_basic_usage.py`
- [ ] Start Streamlit app and test weighted aggregate charts
- [ ] Update documentation
- [ ] Create PR with changes
- [ ] Code review
- [ ] Merge and deploy

---

## Benefits Summary

### Performance
- ✅ **On-demand calculation** - No need to pre-build materialized views
- ✅ **Faster iteration** - Add measures by updating YAML, no build step
- ✅ **Optimized SQL** - Backend adapter generates best SQL for each database

### Code Quality
- ✅ **Separation of concerns** - Business logic in model layer, rendering in UI
- ✅ **DRY principle** - No duplication between Python and SQL calculations
- ✅ **Single source of truth** - Measure definitions in one place (YAML)

### Maintainability
- ✅ **Easier debugging** - Use `explain_measure()` to see generated SQL
- ✅ **Better testing** - Unit tests for each layer
- ✅ **Clear architecture** - Measure → Executor → Adapter → Backend

### Extensibility
- ✅ **Multi-backend support** - Works with DuckDB and Spark
- ✅ **Easy to add measures** - Just update YAML config
- ✅ **Domain patterns** - Weighting strategies are reusable

---

## Next Steps

1. **Review this plan** with the team
2. **Create backup branch** before making changes
3. **Implement Phase 1** (update `_get_weighted_aggregate_data()`)
4. **Test thoroughly** with existing notebooks
5. **Deploy to dev environment** for additional testing
6. **Complete remaining phases** (cleanup, documentation)
7. **Deploy to production**

---

## Questions / Discussion

- Should we keep the old `weighted_aggregate_chart.py` for backward compatibility?
- Do we want to add normalization as a standard measure feature?
- Should materialized views be kept for performance reasons (cached results)?
- Any other exhibits that need similar refactoring?

---

## References

- Implementation Summary: `docs/IMPLEMENTATION_SUMMARY.md`
- Testing Guide: `docs/TESTING_GUIDE.md`
- Backend Abstraction Strategy: `docs/BACKEND_ABSTRACTION_STRATEGY.md`
- Pipeline Tester: `tests/pipeline_tester.py`
- Example Usage: `examples/measure_framework/01_basic_usage.py`
