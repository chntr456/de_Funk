# Weighted Aggregate Refactoring Plan

## Overview

This document outlines the plan to:
1. **Immediate Enhancement**: Allow multiple weighting methods to be selected simultaneously
2. **Architectural Refactoring**: Move weighted aggregate calculations from UI layer to model/silver layer

---

## Part 1: Multi-Method Selection (Quick Win)

### Current State
- Single dropdown selector for weighting method
- One aggregate line per chart
- User must switch between methods to compare

### Proposed Enhancement
- Multi-select checkbox list for weighting methods
- Multiple aggregate lines on same chart (one per selected method)
- Color-coded by weighting method
- Interactive legend to show/hide individual methods

### Implementation

#### UI Changes (app/ui/components/exhibits/weighted_aggregate_chart.py)

```python
# Change from single select to multi-select
selected_methods = st.multiselect(
    "Weighting Methods",
    options=list(weight_methods.keys()),
    default=['Equal Weighted'],  # Default selection
    key=f"{exhibit.id}_weight_methods"
)

# Calculate aggregate for each selected method
all_method_results = []
for method_name in selected_methods:
    method = weight_methods[method_name]
    result_df = calculate_weighted_aggregate(
        pdf, value_col, method, normalize=normalize_weights
    )
    result_df['method'] = method_name  # Add method as a column
    all_method_results.append(result_df)

# Combine all results
combined_df = pd.concat(all_method_results, ignore_index=True)

# Plot with color_by='method'
for method_name in selected_methods:
    method_data = combined_df[combined_df['method'] == method_name]
    fig.add_trace(go.Scatter(
        x=method_data[aggregate_by],
        y=method_data[f'weighted_{value_col}'],
        mode='lines+markers',
        name=method_name,
        # ... styling
    ))
```

### Benefits
- Easy comparison of weighting methods
- Same time period, same data, different weightings
- Interactive legend for toggling visibility
- Minimal code changes (1-2 hours work)

### Limitations
- Still calculating in UI layer (addressed in Part 2)
- Performance impact with many methods selected
- Not cached between sessions

---

## Part 2: Architectural Refactoring (Proper Solution)

### Problem Statement

**Current Architecture:**
```
User Action → UI Component → Calculate Weights → Display
                ↓
         Business Logic in UI Layer ❌
```

**Issues:**
1. Business logic mixed with presentation logic
2. Calculations repeated on every interaction
3. Not reusable across different notebooks
4. Cannot be used in batch/ETL processes
5. Difficult to test and maintain
6. No caching/materialization

### Proposed Architecture

```
Model Definition (YAML)
    ↓
Silver Layer (Pre-calculated or View)
    ↓
NotebookSession (Query via DuckDB)
    ↓
UI Component (Render only)
```

---

## Implementation Plan

### Phase 1: Define Weighted Measures in Model (1 week)

#### 1.1 Extend Schema for Weighted Aggregates

**File:** `app/notebook/schema.py`

```python
@dataclass
class WeightedAggregateMeasure:
    """Definition of a weighted aggregate measure."""
    id: str
    display_name: str
    value_column: str  # Column to aggregate (e.g., "close")
    weighting_method: WeightingMethod
    group_by: List[str]  # e.g., ["trade_date"]
    weight_config: Optional[Dict[str, Any]] = None  # Method-specific config
    format: Optional[str] = None
```

#### 1.2 Update Model Configuration

**File:** `configs/models/company.yaml`

```yaml
measures:
  # Existing simple measures
  avg_close_price:
    source: fact_prices.close
    aggregation: avg
    format: "$#,##0.00"

  # New weighted aggregate measures
  equal_weighted_index:
    type: weighted_aggregate
    value_column: close
    weighting_method: equal
    group_by: [trade_date]
    display_name: "Equal Weighted Price Index"

  volume_weighted_index:
    type: weighted_aggregate
    value_column: close
    weighting_method: volume
    group_by: [trade_date]
    display_name: "Volume Weighted Price Index"

  market_cap_weighted_index:
    type: weighted_aggregate
    value_column: close
    weighting_method: market_cap
    group_by: [trade_date]
    display_name: "Market Cap Weighted Index"

  # Can define for any measure and any grouping
  sector_weighted_volume:
    type: weighted_aggregate
    value_column: volume
    weighting_method: market_cap
    group_by: [trade_date, sector]  # If sector dimension available
```

### Phase 2: Implement Calculation Layer (2 weeks)

#### 2.1 Create Weighted Aggregate Builder

**File:** `models/builders/weighted_aggregate_builder.py`

```python
"""
Builder for materialized weighted aggregate views.

Can be run as part of silver layer build or on-demand.
"""

class WeightedAggregateBuilder:
    """Builds weighted aggregate tables/views in Silver layer."""

    def __init__(self, connection, model_config):
        self.connection = connection
        self.model_config = model_config

    def build_weighted_aggregate(
        self,
        measure_id: str,
        materialize: bool = False
    ):
        """
        Build a weighted aggregate measure.

        Args:
            measure_id: ID of the weighted aggregate measure
            materialize: If True, create table. If False, create view.
        """
        measure = self.model_config.get_measure(measure_id)

        # Generate SQL for weighted aggregate
        sql = self._generate_weighted_aggregate_sql(measure)

        if materialize:
            # Create materialized table
            self.connection.execute(f"""
                CREATE TABLE silver.{measure_id} AS
                {sql}
            """)
        else:
            # Create view (calculated on-demand)
            self.connection.execute(f"""
                CREATE OR REPLACE VIEW silver.{measure_id} AS
                {sql}
            """)

    def _generate_weighted_aggregate_sql(self, measure) -> str:
        """Generate DuckDB SQL for weighted aggregate calculation."""

        method = measure.weighting_method
        value_col = measure.value_column
        group_cols = ', '.join(measure.group_by)

        if method == 'equal':
            return f"""
            SELECT
                {group_cols},
                AVG({value_col}) as weighted_value
            FROM fact_prices
            GROUP BY {group_cols}
            """

        elif method == 'volume':
            return f"""
            SELECT
                {group_cols},
                SUM({value_col} * volume) / SUM(volume) as weighted_value
            FROM fact_prices
            WHERE volume > 0
            GROUP BY {group_cols}
            """

        elif method == 'market_cap':
            return f"""
            SELECT
                {group_cols},
                SUM({value_col} * close * volume) / SUM(close * volume) as weighted_value
            FROM fact_prices
            WHERE volume > 0 AND close > 0
            GROUP BY {group_cols}
            """

        elif method == 'price':
            return f"""
            SELECT
                {group_cols},
                SUM({value_col} * close) / SUM(close) as weighted_value
            FROM fact_prices
            WHERE close > 0
            GROUP BY {group_cols}
            """

        elif method == 'volume_deviation':
            return f"""
            WITH avg_volumes AS (
                SELECT
                    {group_cols},
                    AVG(volume) as avg_volume
                FROM fact_prices
                GROUP BY {group_cols}
            )
            SELECT
                f.{group_cols},
                SUM(f.{value_col} * ABS(f.volume - av.avg_volume) * f.close) /
                    SUM(ABS(f.volume - av.avg_volume) * f.close) as weighted_value
            FROM fact_prices f
            JOIN avg_volumes av USING ({group_cols})
            WHERE f.close > 0
            GROUP BY f.{group_cols}
            """

        # Add other methods...
```

#### 2.2 Integrate with Silver Layer Build

**File:** `scripts/build_silver_layer.py`

```python
from models.builders.weighted_aggregate_builder import WeightedAggregateBuilder

def build_silver_layer():
    # ... existing code ...

    # Build weighted aggregates
    print("\n5. Building weighted aggregate measures...")
    wa_builder = WeightedAggregateBuilder(connection, model_config)

    # Create as views (calculated on-demand)
    wa_builder.build_weighted_aggregate('equal_weighted_index', materialize=False)
    wa_builder.build_weighted_aggregate('volume_weighted_index', materialize=False)
    wa_builder.build_weighted_aggregate('market_cap_weighted_index', materialize=False)

    print("✓ Weighted aggregate views created")
```

### Phase 3: Update NotebookSession to Use Model Measures (1 week)

#### 3.1 Modify Exhibit Data Retrieval

**File:** `app/notebook/api/notebook_session.py`

```python
def get_exhibit_data(self, exhibit_id: str):
    """Get data for an exhibit, handling weighted aggregates."""

    exhibit = self._get_exhibit_by_id(exhibit_id)

    if exhibit.type == ExhibitType.WEIGHTED_AGGREGATE_CHART:
        # New logic: query pre-defined weighted measures
        return self._get_weighted_aggregate_data(exhibit)
    else:
        # Existing logic
        return self._get_standard_exhibit_data(exhibit)

def _get_weighted_aggregate_data(self, exhibit):
    """Query weighted aggregate measures from silver layer."""

    # Get list of weighted measures to query
    measure_ids = exhibit.value_measures  # e.g., ["equal_weighted_index", "volume_weighted_index"]

    results = []
    for measure_id in measure_ids:
        # Query the measure view/table
        sql = f"""
        SELECT
            {exhibit.aggregate_by},
            weighted_value,
            '{measure_id}' as measure_id
        FROM silver.{measure_id}
        WHERE {self._build_filter_clause()}
        ORDER BY {exhibit.aggregate_by}
        """

        df = self.connection.execute(sql).fetch_df()
        results.append(df)

    # Combine all measures
    return pd.concat(results, ignore_index=True)
```

### Phase 4: Simplify UI Component (1 week)

#### 4.1 Update Weighted Aggregate Chart Renderer

**File:** `app/ui/components/exhibits/weighted_aggregate_chart.py`

```python
def render_weighted_aggregate_chart(exhibit, pdf: pd.DataFrame):
    """
    Render weighted aggregate chart.

    Now just a simple renderer - all calculations done in model layer.
    """

    st.subheader(exhibit.title)

    if exhibit.description:
        st.caption(exhibit.description)

    if pdf.empty:
        st.info("No data available for selected filters")
        return

    # Data already includes all selected weighted measures
    # Just need to plot them

    # Group by measure_id (each measure is a different weighting method)
    fig = go.Figure()

    for measure_id in pdf['measure_id'].unique():
        measure_data = pdf[pdf['measure_id'] == measure_id]

        fig.add_trace(go.Scatter(
            x=measure_data[exhibit.aggregate_by],
            y=measure_data['weighted_value'],
            mode='lines+markers',
            name=measure_id.replace('_', ' ').title(),
            line=dict(width=2.5),
            marker=dict(size=6),
        ))

    # Apply theme and render
    _apply_theme(fig)
    st.plotly_chart(fig, use_container_width=True)
```

**Benefits:**
- UI code reduced by ~80%
- No business logic in UI
- Just visualization

### Phase 5: Update Notebook YAML Configuration (1 day)

**File:** `configs/notebooks/aggregate_stock_analysis.yaml`

```yaml
exhibits:
  - id: multi_method_comparison
    type: weighted_aggregate_chart
    title: "Price Index Comparison (Multiple Weighting Methods)"
    description: "Compare different weighting methods side-by-side"
    source: "company.weighted_aggregates"  # Special source
    aggregate_by: trade_date
    value_measures:
      - equal_weighted_index
      - volume_weighted_index
      - market_cap_weighted_index
      - volume_deviation_weighted_index
```

**Note:** No UI-level method selection needed - measures are pre-defined in model!

---

## Architecture Benefits

### Before (Current)
```
❌ Business logic in UI layer
❌ Calculations on every render
❌ Not reusable
❌ Hard to test
❌ No caching
❌ Tight coupling
```

### After (Proposed)
```
✅ Business logic in model layer
✅ Calculations in silver layer (cached)
✅ Reusable across notebooks
✅ Easy to test (SQL-based)
✅ DuckDB-optimized queries
✅ Loose coupling
✅ Can batch process
✅ Consistent definitions
```

---

## Migration Strategy

### Option A: Big Bang (Not Recommended)
- Implement all phases at once
- High risk, long development time
- App unavailable during refactor

### Option B: Incremental (Recommended)

#### Step 1: Add multi-select to current UI (1 day)
- Quick win for users
- No architecture changes
- **File:** `app/ui/components/exhibits/weighted_aggregate_chart.py`

#### Step 2: Build parallel system (2 weeks)
- Implement model-based measures alongside current UI calculations
- No user impact
- **Files:** Schema, builders, model configs

#### Step 3: Add feature flag (1 day)
- Toggle between old and new system
- Test in production with subset of users
- **File:** `app/notebook/api/notebook_session.py`

```python
USE_MODEL_WEIGHTED_AGGREGATES = os.getenv('USE_MODEL_WEIGHTED_AGGREGATES', 'false').lower() == 'true'

def _get_weighted_aggregate_data(self, exhibit):
    if USE_MODEL_WEIGHTED_AGGREGATES:
        return self._get_weighted_aggregate_data_from_model(exhibit)
    else:
        return self._get_weighted_aggregate_data_legacy(exhibit)
```

#### Step 4: Migrate notebooks incrementally (1 week)
- Update one notebook at a time
- Validate results match
- Roll back if issues

#### Step 5: Remove old code (1 day)
- Delete legacy calculation functions
- Remove feature flag
- Update documentation

---

## Performance Comparison

### Current (UI Layer)
```python
# Python/NumPy calculations on every render
# For 1000 rows, 5 stocks, 30 days:
# ~50-100ms per weighting method
# Multiple methods = linear scaling
```

### Proposed (Silver Layer)
```sql
-- DuckDB query on pre-built view
-- For same data:
-- ~5-10ms per query (columnar storage)
-- Multiple methods = cached, no scaling
```

**Expected improvement: 5-10x faster**

---

## Testing Strategy

### Unit Tests
```python
# tests/models/test_weighted_aggregate_builder.py
def test_equal_weighted_sql():
    """Test SQL generation for equal weighted aggregate."""

def test_volume_weighted_sql():
    """Test SQL generation for volume weighted aggregate."""

def test_weighted_aggregate_calculation():
    """Test actual calculation results."""
    # Compare against known correct values
```

### Integration Tests
```python
# tests/integration/test_weighted_aggregates.py
def test_weighted_aggregate_end_to_end():
    """Test full flow from model to UI."""

def test_backward_compatibility():
    """Ensure existing notebooks still work."""
```

### Validation
- Compare old vs new calculations on same data
- Should match to within floating point precision
- Document any intentional differences

---

## Rollout Timeline

| Phase | Duration | Risk | Effort |
|-------|----------|------|--------|
| Multi-select UI | 1 day | Low | Low |
| Schema extensions | 2 days | Low | Medium |
| Weighted aggregate builder | 1 week | Medium | High |
| NotebookSession integration | 1 week | Medium | Medium |
| UI simplification | 3 days | Low | Low |
| Testing & validation | 3 days | Low | Medium |
| Documentation | 2 days | Low | Low |
| **Total** | **3-4 weeks** | | |

---

## Risks & Mitigations

### Risk 1: Breaking existing notebooks
**Mitigation:** Feature flag, incremental migration, rollback plan

### Risk 2: Performance degradation
**Mitigation:** Benchmark before/after, use views vs materialized tables

### Risk 3: SQL complexity for advanced weightings
**Mitigation:** Start with simple methods, add complex ones incrementally

### Risk 4: Loss of interactive method switching
**Mitigation:** Pre-define common methods, allow custom methods via YAML

---

## Decision: Which Approach?

### Recommendation: **Incremental Migration (Option B)**

1. **Week 1:** Implement multi-select in current UI ← **Quick win for users**
2. **Week 2-3:** Build model layer infrastructure (parallel to existing)
3. **Week 4:** Feature flag, testing, gradual rollout
4. **Week 5:** Remove legacy code

This approach:
- Delivers immediate value
- Reduces risk
- Allows for testing and validation
- Maintains backward compatibility
- Can be paused/rolled back at any point

---

## Next Steps

To proceed, we need to decide:

1. **Immediate:** Implement multi-select (1 day work)?
2. **Long-term:** Full refactoring (3-4 weeks work)?
3. **Hybrid:** Multi-select now, refactor later?

**My recommendation: Hybrid approach**
- Do multi-select now (satisfies immediate need)
- Plan refactoring for next sprint/milestone
- Gives time to validate architecture before committing

What would you like to prioritize?
