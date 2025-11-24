# Company Model Architecture Review & Design Proposal

**Date:** 2025-11-12
**Status:** Draft for Review
**Goal:** Ensure good sustainable architecture for measures, aggregates, and domain-specific calculations

---

## Executive Summary

This document reviews the current architecture of the company model, focusing on:
1. **Where measures and aggregate lineage is stored**
2. **Architectural issues with weighted aggregates**
3. **Proposal for a cleaner, more sustainable vessel for domain-specific calculations**
4. **ETF use case as an expansion example**

### Key Findings

✅ **Strengths:**
- YAML-driven declarative design (87% config, 13% code)
- Clean graph-based model structure
- Good separation of concerns at the table level

❌ **Issues:**
- Measure lineage is scattered and unclear
- Weighted aggregates feel detached and company-specific
- No unified framework for domain-specific calculations
- Import paths broken (script imports from non-existent `models/builders/`)
- Inconsistency between simple measures and weighted measures

---

## Part 1: Current Architecture Analysis

### 1.1 Where Measures Are Stored

**Measure Definitions:** `configs/models/company.yaml`

```yaml
measures:
  # Simple aggregates
  avg_close_price:
    source: fact_prices.close
    aggregation: avg
    data_type: double

  # Computed measures
  market_cap:
    type: computed
    source: fact_prices.close
    expression: "close * volume"
    aggregation: avg

  # Weighted aggregates (the problem child)
  equal_weighted_index:
    type: weighted_aggregate
    source: fact_prices.close
    weighting_method: equal
    group_by: [trade_date]
```

**Calculation Logic - Scattered Across Multiple Locations:**

1. **Simple/Computed Measures:** `models/base/model.py:717-823`
   - `BaseModel.calculate_measure_by_entity()`
   - Only works with Spark backend
   - Reads YAML config and generates PySpark code
   - Returns aggregated DataFrame

2. **Weighted Aggregates:** `models/implemented/company/weighted_aggregate_builder.py`
   - Separate builder class
   - Only works with DuckDB backend
   - Reads same YAML config
   - Generates SQL and creates views/tables
   - **Not integrated with BaseModel**

3. **Invocation:** `scripts/build_weighted_aggregates_duckdb.py`
   - Standalone script
   - **Broken import path:** `from models.builders.weighted_aggregate_builder import ...`
   - The directory `models/builders/` doesn't exist!
   - Actual location: `models/implemented/company/weighted_aggregate_builder.py`

### 1.2 The Problem: No Clear Lineage or Ownership

```
┌─────────────────────────────────────────────────────────┐
│ YAML Config (company.yaml)                              │
│ ✓ Single source of truth for measure definitions        │
└─────────────────────────────────────────────────────────┘
                        │
                        ├── Simple Measures
                        │   ↓
          ┌─────────────────────────────────────┐
          │ BaseModel.calculate_measure_by_entity │  ← Spark only
          │ (Python/PySpark code generation)       │
          └─────────────────────────────────────┘
                        │
                        └── Weighted Measures
                            ↓
          ┌─────────────────────────────────────┐
          │ WeightedAggregateBuilder             │  ← DuckDB only
          │ (SQL generation, separate builder)   │  ← Company-specific
          └─────────────────────────────────────┘  ← Detached from model
                            │
                            ↓
                   ❌ Broken import path
```

**Issues:**
1. ❌ Two different execution paths for measures
2. ❌ Backend inconsistency (Spark vs DuckDB)
3. ❌ Weighted aggregates not accessible via CompanyModel methods
4. ❌ Broken import path indicates architectural confusion
5. ❌ No unified measure execution framework
6. ❌ Can't easily add new measure types

### 1.3 Weighted Aggregates Are "Leftover Code"

The user's instinct is correct - weighted aggregates feel detached because:

1. **Location mismatch:**
   - Lives in `models/implemented/company/` (company-specific)
   - But weighting is a general concept (applies to ETFs, portfolios, sectors, etc.)
   - Script tries to import from `models/builders/` (general location that doesn't exist)

2. **Not integrated with model:**
   - CompanyModel has no methods to access weighted measures
   - Can't call `model.calculate_measure_by_ticker('equal_weighted_index')`
   - Must manually query the view: `SELECT * FROM equal_weighted_index`

3. **Separate lifecycle:**
   - Built by separate script, not part of model build
   - Not included in `model.build()` or `model.write_tables()`
   - Feels like an afterthought

4. **Backend-specific:**
   - Only works with DuckDB
   - Simple measures only work with Spark
   - No unified abstraction

---

## Part 2: Root Cause Analysis

### 2.1 The Core Problem

**There is no unified "Measure" abstraction.**

Currently we have:
- YAML definitions (declarative)
- Scattered Python implementations (imperative)
- No single execution path
- No measure registry or factory pattern

What we need:
```
Measure Definition (YAML)
    ↓
Measure Registry/Factory
    ↓
Measure Executor (backend-agnostic)
    ↓
Results (DataFrame/Arrow/DuckDB)
```

### 2.2 Why Weighted Aggregates Feel Detached

They are a **domain-specific calculation pattern** that has no proper home:

- Too specific for `BaseModel` (general model framework)
- Too general for `CompanyModel` (applies to ETFs, portfolios, sectors)
- Currently stuck in limbo at `models/implemented/company/weighted_aggregate_builder.py`

**The real question:** Where should domain-specific calculation patterns live?

---

## Part 3: Proposed Architecture - "Cleaner Vessel"

### 3.1 Design Principles

1. **Unified Measure Framework:** All measures go through same execution path
2. **Backend Agnostic:** Works with both Spark and DuckDB
3. **Extensible:** Easy to add new measure types
4. **Composable:** Measures can reference other measures
5. **Domain-Specific Patterns:** Clear home for calculation patterns (weighting, windowing, etc.)
6. **First-Class Integration:** Accessible via model methods

### 3.2 Proposed Directory Structure

```
models/
├── base/
│   ├── model.py                    # BaseModel (graph, tables, schema)
│   └── measures/
│       ├── __init__.py
│       ├── executor.py            # NEW: Unified measure execution
│       ├── registry.py            # NEW: Measure type registry
│       └── base_measure.py        # NEW: Abstract base class
│
├── measures/                       # NEW: Calculation pattern library
│   ├── __init__.py
│   ├── simple.py                  # Simple aggregations (avg, sum, etc.)
│   ├── computed.py                # Computed expressions
│   ├── weighted.py                # Weighted aggregation patterns
│   ├── window.py                  # Window functions (rolling, rank, etc.)
│   ├── ratio.py                   # Ratio calculations
│   └── custom.py                  # Custom SQL/expression measures
│
├── domains/                        # NEW: Domain-specific extensions
│   ├── __init__.py
│   ├── equities/
│   │   ├── measures.py            # Equity-specific measures
│   │   └── weighting.py           # Equity weighting strategies
│   ├── etf/
│   │   ├── measures.py            # ETF-specific measures
│   │   └── weighting.py           # ETF weighting (holdings-based)
│   └── portfolio/
│       ├── measures.py            # Portfolio measures
│       └── attribution.py         # Attribution calculations
│
└── implemented/
    ├── company/
    │   └── model.py               # CompanyModel (convenience methods only)
    └── ...
```

### 3.3 Key Components

#### Component 1: Unified Measure Abstraction

**File:** `models/base/measures/base_measure.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum

class MeasureType(Enum):
    """Types of measures."""
    SIMPLE = "simple"              # Direct aggregation (avg, sum, etc.)
    COMPUTED = "computed"          # Expression-based (close * volume)
    WEIGHTED = "weighted"          # Weighted aggregations
    WINDOW = "window"              # Window functions (rolling, lag, etc.)
    RATIO = "ratio"                # Ratios and percentages
    CUSTOM = "custom"              # Custom SQL/code

class BaseMeasure(ABC):
    """Base class for all measure types."""

    def __init__(self, config: Dict[str, Any]):
        self.name = config['name']
        self.description = config.get('description', '')
        self.source = config['source']
        self.data_type = config.get('data_type', 'double')
        self.tags = config.get('tags', [])

    @abstractmethod
    def execute_spark(self, model, entity_column: str, **kwargs):
        """Execute measure using Spark backend."""
        pass

    @abstractmethod
    def execute_duckdb(self, connection, model, entity_column: str, **kwargs):
        """Execute measure using DuckDB backend."""
        pass

    @abstractmethod
    def to_sql(self, dialect: str = 'duckdb') -> str:
        """Generate SQL for this measure."""
        pass
```

#### Component 2: Measure Registry

**File:** `models/base/measures/registry.py`

```python
from typing import Dict, Type
from .base_measure import BaseMeasure, MeasureType

class MeasureRegistry:
    """Registry for measure type implementations."""

    _registry: Dict[MeasureType, Type[BaseMeasure]] = {}

    @classmethod
    def register(cls, measure_type: MeasureType):
        """Decorator to register measure implementations."""
        def decorator(measure_class: Type[BaseMeasure]):
            cls._registry[measure_type] = measure_class
            return measure_class
        return decorator

    @classmethod
    def create_measure(cls, config: Dict[str, Any]) -> BaseMeasure:
        """Factory method to create measure from config."""
        measure_type = MeasureType(config.get('type', 'simple'))
        measure_class = cls._registry.get(measure_type)

        if not measure_class:
            raise ValueError(f"Unknown measure type: {measure_type}")

        return measure_class(config)
```

#### Component 3: Weighted Measure Implementation

**File:** `models/measures/weighted.py`

```python
from typing import Any, Dict, Optional
from models.base.measures.base_measure import BaseMeasure, MeasureType
from models.base.measures.registry import MeasureRegistry

@MeasureRegistry.register(MeasureType.WEIGHTED)
class WeightedMeasure(BaseMeasure):
    """
    Weighted aggregate measure.

    Calculates weighted aggregations across multiple entities (stocks, ETFs, etc.)
    using various weighting schemes.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.weighting_method = config.get('weighting_method', 'equal')
        self.group_by = config.get('group_by', ['trade_date'])
        self.weight_column = config.get('weight_column')  # Optional explicit weight column

    def execute_duckdb(self, connection, model, entity_column: str = None, **kwargs):
        """Execute weighted measure in DuckDB."""
        sql = self.to_sql(dialect='duckdb')

        # Get source table from model
        table_name, value_col = self._parse_source()
        table_path = model.get_table_path(table_name)

        # Execute query
        query = f"""
        WITH source_data AS (
            SELECT * FROM read_parquet('{table_path}')
        )
        {sql}
        """

        return connection.execute(query).fetch_df()

    def to_sql(self, dialect: str = 'duckdb') -> str:
        """Generate SQL for weighted aggregate."""
        table_name, value_col = self._parse_source()
        group_cols = ', '.join(self.group_by)

        # Delegate to weighting strategy
        from models.domains.equities.weighting import get_weighting_strategy
        strategy = get_weighting_strategy(self.weighting_method)

        return strategy.generate_sql(
            source_table=table_name,
            value_column=value_col,
            group_by=group_cols,
            weight_column=self.weight_column,
            dialect=dialect
        )

    def _parse_source(self):
        """Parse source into table and column."""
        if '.' not in self.source:
            raise ValueError(f"Source must be 'table.column', got: {self.source}")
        return self.source.rsplit('.', 1)
```

#### Component 4: Weighting Strategies (Domain-Specific)

**File:** `models/domains/equities/weighting.py`

```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict

class WeightingMethod(Enum):
    """Weighting methods for equities."""
    EQUAL = "equal"
    VOLUME = "volume"
    MARKET_CAP = "market_cap"
    PRICE = "price"
    VOLUME_DEVIATION = "volume_deviation"
    VOLATILITY = "volatility"

class WeightingStrategy(ABC):
    """Base class for weighting strategies."""

    @abstractmethod
    def generate_sql(
        self,
        source_table: str,
        value_column: str,
        group_by: str,
        weight_column: str = None,
        dialect: str = 'duckdb'
    ) -> str:
        """Generate SQL for this weighting method."""
        pass

class EqualWeightStrategy(WeightingStrategy):
    """Equal weighting (simple average)."""

    def generate_sql(self, source_table, value_column, group_by, weight_column=None, dialect='duckdb'):
        return f"""
        SELECT
            {group_by},
            AVG({value_column}) as weighted_value,
            COUNT(*) as entity_count
        FROM {source_table}
        WHERE {value_column} IS NOT NULL
        GROUP BY {group_by}
        ORDER BY {group_by}
        """

class VolumeWeightStrategy(WeightingStrategy):
    """Volume-weighted average."""

    def generate_sql(self, source_table, value_column, group_by, weight_column=None, dialect='duckdb'):
        return f"""
        SELECT
            {group_by},
            SUM({value_column} * volume) / NULLIF(SUM(volume), 0) as weighted_value,
            COUNT(*) as entity_count,
            SUM(volume) as total_volume
        FROM {source_table}
        WHERE {value_column} IS NOT NULL
          AND volume IS NOT NULL
          AND volume > 0
        GROUP BY {group_by}
        ORDER BY {group_by}
        """

class MarketCapWeightStrategy(WeightingStrategy):
    """Market cap weighted (price × volume as proxy)."""

    def generate_sql(self, source_table, value_column, group_by, weight_column=None, dialect='duckdb'):
        return f"""
        SELECT
            {group_by},
            SUM({value_column} * close * volume) / NULLIF(SUM(close * volume), 0) as weighted_value,
            COUNT(*) as entity_count,
            SUM(close * volume) as total_market_cap
        FROM {source_table}
        WHERE {value_column} IS NOT NULL
          AND close IS NOT NULL
          AND volume IS NOT NULL
          AND close > 0
          AND volume > 0
        GROUP BY {group_by}
        ORDER BY {group_by}
        """

# Registry of strategies
_STRATEGIES: Dict[WeightingMethod, WeightingStrategy] = {
    WeightingMethod.EQUAL: EqualWeightStrategy(),
    WeightingMethod.VOLUME: VolumeWeightStrategy(),
    WeightingMethod.MARKET_CAP: MarketCapWeightStrategy(),
    # ... other strategies
}

def get_weighting_strategy(method: str) -> WeightingStrategy:
    """Get weighting strategy by name."""
    method_enum = WeightingMethod(method)
    strategy = _STRATEGIES.get(method_enum)

    if not strategy:
        raise ValueError(f"Unknown weighting method: {method}")

    return strategy
```

#### Component 5: Measure Executor

**File:** `models/base/measures/executor.py`

```python
from typing import Any, Dict, Optional
from .registry import MeasureRegistry

class MeasureExecutor:
    """
    Unified executor for all measure types.

    Provides single entry point for measure calculation,
    abstracting backend details.
    """

    def __init__(self, model, backend: str = 'duckdb'):
        self.model = model
        self.backend = backend

    def execute_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Execute a measure from model configuration.

        Args:
            measure_name: Name of measure from config
            entity_column: Optional entity column to group by
            limit: Optional limit for results
            **kwargs: Additional measure-specific parameters

        Returns:
            DataFrame with measure results
        """
        # Get measure config from model
        measure_config = self.model.model_cfg.get('measures', {}).get(measure_name)

        if not measure_config:
            available = list(self.model.model_cfg.get('measures', {}).keys())
            raise ValueError(
                f"Measure '{measure_name}' not defined. Available: {available}"
            )

        # Add name to config
        measure_config = {**measure_config, 'name': measure_name}

        # Create measure instance using registry
        measure = MeasureRegistry.create_measure(measure_config)

        # Execute using appropriate backend
        if self.backend == 'duckdb':
            result = measure.execute_duckdb(
                self.model.connection,
                self.model,
                entity_column=entity_column,
                **kwargs
            )
        elif self.backend == 'spark':
            result = measure.execute_spark(
                self.model,
                entity_column=entity_column,
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

        # Apply limit if specified
        if limit and result is not None:
            result = result.head(limit) if self.backend == 'duckdb' else result.limit(limit)

        return result
```

#### Component 6: Integration with BaseModel

**File:** `models/base/model.py` (modifications)

```python
class BaseModel:
    """Base model class with unified measure execution."""

    def __init__(self, ...):
        # ... existing initialization ...

        # NEW: Measure executor
        self._measure_executor = None

    @property
    def measures(self):
        """Get measure executor."""
        if self._measure_executor is None:
            from models.base.measures.executor import MeasureExecutor
            self._measure_executor = MeasureExecutor(self, backend=self.backend)
        return self._measure_executor

    def calculate_measure(
        self,
        measure_name: str,
        entity_column: Optional[str] = None,
        limit: Optional[int] = None,
        **kwargs
    ):
        """
        Calculate any measure defined in model config.

        Replaces calculate_measure_by_entity with unified executor.
        """
        return self.measures.execute_measure(
            measure_name=measure_name,
            entity_column=entity_column,
            limit=limit,
            **kwargs
        )
```

### 3.4 Usage Examples

#### Simple Measure
```python
# In YAML config
measures:
  avg_close_price:
    source: fact_prices.close
    aggregation: avg

# In Python
df = company_model.calculate_measure('avg_close_price', entity_column='ticker', limit=10)
```

#### Weighted Measure
```python
# In YAML config
measures:
  volume_weighted_index:
    type: weighted
    source: fact_prices.close
    weighting_method: volume
    group_by: [trade_date]

# In Python
df = company_model.calculate_measure('volume_weighted_index')
```

#### All measures use the same interface! 🎉

---

## Part 4: ETF Use Case - Expansion Example

### 4.1 ETF-Specific Requirements

ETFs have unique characteristics:
1. **Holdings-based weighting:** Weight by actual holdings percentage
2. **Sector exposure:** Calculate sector weights from holdings
3. **Tracking metrics:** Compare ETF performance to underlying index
4. **Creation/redemption flows:** Track changes in holdings

### 4.2 Proposed ETF Model

**File:** `configs/models/etf.yaml`

```yaml
version: 1
model: etf
tags: [etf, portfolio, us]

depends_on:
  - core
  - company  # For underlying holdings

schema:
  dimensions:
    dim_etf:
      path: dims/dim_etf
      columns:
        etf_ticker: string
        etf_name: string
        fund_family: string
        expense_ratio: double
        inception_date: date
        category: string  # equity, bond, commodity, etc.
        index_tracked: string
      primary_key: [etf_ticker]

    dim_etf_holdings:
      path: dims/dim_etf_holdings
      description: "ETF holdings (point-in-time)"
      columns:
        etf_ticker: string
        holding_ticker: string
        as_of_date: date
        weight_percent: double
        shares_held: long
        market_value: double
      primary_key: [etf_ticker, holding_ticker, as_of_date]

  facts:
    fact_etf_prices:
      path: facts/fact_etf_prices
      columns:
        trade_date: date
        etf_ticker: string
        # ... OHLCV data ...

measures:
  # Simple measures (inherited pattern)
  avg_expense_ratio:
    source: dim_etf.expense_ratio
    aggregation: avg

  # Weighted measures using HOLDINGS
  holdings_weighted_return:
    type: weighted
    source: fact_prices.close  # Company fact table
    weighting_method: etf_holdings  # NEW: Holdings-based weighting
    group_by: [trade_date]
    weight_source: dim_etf_holdings.weight_percent  # Explicit weight column

  sector_weighted_exposure:
    type: weighted
    source: company.dim_company.sector  # Cross-model reference
    weighting_method: etf_holdings
    group_by: [sector]
    weight_source: dim_etf_holdings.weight_percent
```

### 4.3 ETF-Specific Weighting Strategy

**File:** `models/domains/etf/weighting.py`

```python
from models.domains.equities.weighting import WeightingStrategy

class HoldingsWeightStrategy(WeightingStrategy):
    """
    Weight by actual ETF holdings.

    Uses explicit weight column from holdings table.
    """

    def generate_sql(
        self,
        source_table: str,
        value_column: str,
        group_by: str,
        weight_column: str,
        dialect: str = 'duckdb'
    ) -> str:
        if not weight_column:
            raise ValueError("Holdings weighting requires explicit weight_column")

        return f"""
        WITH holdings AS (
            SELECT
                {group_by},
                holding_ticker,
                {weight_column} / 100.0 as weight  -- Convert percent to decimal
            FROM dim_etf_holdings
            WHERE {weight_column} IS NOT NULL
        )
        SELECT
            h.{group_by},
            SUM(s.{value_column} * h.weight) as weighted_value,
            COUNT(DISTINCT h.holding_ticker) as holding_count,
            SUM(h.weight) as total_weight  -- Should sum to 1.0
        FROM holdings h
        JOIN {source_table} s ON h.holding_ticker = s.ticker
        WHERE s.{value_column} IS NOT NULL
        GROUP BY h.{group_by}
        ORDER BY h.{group_by}
        """
```

### 4.4 ETF Usage Example

```python
from models.implemented.etf.model import ETFModel

# Initialize model
etf_model = ETFModel(ctx.connection, ctx.storage, ctx.repo)

# Calculate holdings-weighted return for SPY
spy_return = etf_model.calculate_measure(
    'holdings_weighted_return',
    filters={'etf_ticker': 'SPY'},
    date_range=('2024-01-01', '2024-12-31')
)

# Calculate sector exposure
sector_exposure = etf_model.calculate_measure(
    'sector_weighted_exposure',
    filters={'etf_ticker': 'SPY'},
    as_of_date='2024-12-01'
)
```

---

## Part 5: Implementation Plan

### Phase 1: Foundation (Week 1-2)

**Goal:** Build measure framework without breaking existing code

1. Create new directory structure:
   - `models/base/measures/`
   - `models/measures/`
   - `models/domains/`

2. Implement base abstractions:
   - `BaseMeasure`
   - `MeasureRegistry`
   - `MeasureExecutor`

3. Implement simple measure type:
   - `SimpleMeasure` (avg, sum, min, max, count)
   - Works with both Spark and DuckDB

4. Add to BaseModel (parallel to existing):
   - `model.measures` property
   - `model.calculate_measure()` method
   - Keep `calculate_measure_by_entity()` for backward compatibility

**Deliverables:**
- ✅ New measure framework operational
- ✅ Existing code unchanged
- ✅ Tests passing

### Phase 2: Weighted Measures (Week 3-4)

**Goal:** Migrate weighted aggregates to new framework

1. Implement `WeightedMeasure` class
2. Migrate weighting strategies to `models/domains/equities/weighting.py`
3. Create `models/builders/` directory (proper location)
4. Move and refactor `WeightedAggregateBuilder`:
   - Use new `WeightedMeasure` class internally
   - Make backend-agnostic
5. Fix broken import in `scripts/build_weighted_aggregates_duckdb.py`
6. Update CompanyModel to use new measure framework

**Deliverables:**
- ✅ Weighted measures integrated
- ✅ Import paths fixed
- ✅ Works with both backends
- ✅ Backward compatible

### Phase 3: ETF Model (Week 5-6)

**Goal:** Validate extensibility with real use case

1. Create `configs/models/etf.yaml`
2. Implement `models/implemented/etf/model.py`
3. Add holdings-based weighting strategy
4. Create sample ETF data
5. Build and validate ETF model
6. Create example notebook

**Deliverables:**
- ✅ ETF model functional
- ✅ Holdings-based weighting working
- ✅ Demonstrates framework extensibility

### Phase 4: Migration & Cleanup (Week 7-8)

**Goal:** Complete migration and remove legacy code

1. Update all measure calculations to use new framework
2. Deprecate `calculate_measure_by_entity()`
3. Remove old weighted aggregate builder
4. Update documentation
5. Update all example notebooks
6. Performance testing and optimization

**Deliverables:**
- ✅ Full migration complete
- ✅ Legacy code removed
- ✅ Documentation updated
- ✅ Performance validated

---

## Part 6: Benefits & Impact

### 6.1 Architecture Benefits

✅ **Unified Framework:**
- Single entry point: `model.calculate_measure()`
- All measure types use same interface
- Consistent behavior across backends

✅ **Clear Ownership:**
- Measures defined in YAML (single source of truth)
- Execution logic in `models/measures/` (general patterns)
- Domain logic in `models/domains/` (specific strategies)
- No confusion about where code belongs

✅ **Extensibility:**
- Easy to add new measure types (register new class)
- Easy to add new weighting methods (add strategy class)
- Easy to add domain-specific logic (create domain module)

✅ **Testability:**
- Each measure type is independently testable
- Strategies can be unit tested
- End-to-end integration tests

✅ **Backend Agnostic:**
- Works with both Spark and DuckDB
- Easy to add new backends
- SQL generation abstracted

### 6.2 Developer Experience

**Before:**
```python
# Simple measure
df1 = model.calculate_measure_by_entity('avg_close', 'ticker')  # Spark only

# Weighted measure
# ??? No model method exists ???
# Must manually query: SELECT * FROM equal_weighted_index
```

**After:**
```python
# All measures use same interface!
df1 = model.calculate_measure('avg_close', entity_column='ticker')
df2 = model.calculate_measure('volume_weighted_index')
df3 = model.calculate_measure('sector_exposure', filters={'etf': 'SPY'})

# Works with both Spark and DuckDB
# Backend automatically detected
```

### 6.3 ETF/Portfolio Use Cases Unlocked

With this architecture, implementing ETFs, portfolios, and custom indices becomes straightforward:

1. **ETF Tracking:**
   - Holdings-based weighting
   - Sector exposure
   - Tracking error vs index

2. **Portfolio Analysis:**
   - Custom portfolio weights
   - Performance attribution
   - Risk metrics

3. **Custom Indices:**
   - Thematic indices (ESG, tech, etc.)
   - Equal-weighted S&P 500 alternative
   - Factor-based indices

4. **Cross-Asset:**
   - Multi-asset portfolio (stocks + bonds + commodities)
   - Currency-hedged returns
   - Risk-adjusted returns

---

## Part 7: Risk Assessment

### 7.1 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing code | Medium | High | Parallel implementation, feature flags |
| Performance regression | Low | Medium | Benchmark before/after, optimize SQL |
| Complexity increase | Low | Low | Clear abstractions, good documentation |
| Migration time overrun | Medium | Low | Incremental phases, can pause anytime |
| Team learning curve | Medium | Low | Examples, documentation, pair programming |

### 7.2 Success Criteria

✅ All existing functionality preserved
✅ No performance regression (±5%)
✅ Import paths all valid
✅ Can implement ETF model in < 1 day
✅ Documentation complete
✅ All tests passing

---

## Part 8: Recommendations

### Immediate Actions (This Week)

1. **Review this proposal** with team
2. **Validate approach** with stakeholders
3. **Prioritize phases** based on business needs
4. **Assign resources** for implementation

### Short-Term (Next 2 Weeks)

1. **Implement Phase 1** (Foundation)
2. **Create proof-of-concept** for one measure type
3. **Validate performance** with real data
4. **Get feedback** from users

### Medium-Term (Next 2 Months)

1. **Complete Phase 2** (Weighted measures)
2. **Implement Phase 3** (ETF model)
3. **Migrate existing code** incrementally
4. **Update documentation** and examples

### Long-Term (Next Quarter)

1. **Complete Phase 4** (Migration & cleanup)
2. **Add advanced measure types** (window, ratio, etc.)
3. **Expand domain modules** (fixed income, crypto, etc.)
4. **Performance optimization** and caching

---

## Conclusion

The current architecture has strong foundations (YAML-driven, graph-based, clean separation of concerns) but suffers from scattered measure execution logic and no clear home for domain-specific calculations like weighted aggregates.

**The proposed architecture provides:**
- ✅ A unified, extensible measure framework
- ✅ Clear ownership and lineage for all calculations
- ✅ A proper home for domain-specific patterns
- ✅ Easy path to implement ETFs and other use cases
- ✅ Sustainable architecture that can grow with the product

**Next Steps:**
1. Review and discuss this proposal
2. Make any necessary adjustments
3. Begin Phase 1 implementation
4. Validate with real use cases

---

**Questions? Concerns? Let's discuss!**
