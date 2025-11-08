# Models TODOs

This document tracks improvements, enhancements, and new model ideas for the de_Funk model layer.

**Last Updated:** 2025-11-08

---

## Table of Contents

- [Core Model Framework](#core-model-framework)
- [Model Features](#model-features)
- [New Model Ideas](#new-model-ideas)
- [Cross-Model Features](#cross-model-features)
- [Model Testing](#model-testing)
- [Model Performance](#model-performance)

---

## Core Model Framework

### Critical Priority

#### MOD-CORE-001: Add Comprehensive Tests for write_tables()
**Status:** Not Started
**Priority:** Critical
**Effort:** 3-5 days

**Description:**
The new `BaseModel.write_tables()` method needs comprehensive test coverage.

**Test Coverage Needed:**
- [ ] Write with default settings
- [ ] Write with custom output path
- [ ] Write with different formats (parquet, delta)
- [ ] Write with partitioning
- [ ] Write with optimized writer enabled/disabled
- [ ] Write with custom sort columns
- [ ] Handle empty DataFrames
- [ ] Handle missing columns
- [ ] Verify file structure
- [ ] Verify row counts
- [ ] Test error handling (permissions, disk space)

**Test Structure:**
```python
class TestBaseModelWriteTables:
    def test_write_defaults(self, spark, tmp_path):
        # Test default write behavior
        pass

    def test_write_with_partitioning(self, spark, tmp_path):
        # Test partitioned writes
        pass

    def test_write_error_handling(self, spark, tmp_path):
        # Test error cases
        pass
```

---

#### MOD-CORE-002: Implement Model Validation
**Status:** Not Started
**Priority:** Critical
**Effort:** 5-7 days

**Description:**
Validate model configuration and graph structure before building.

**Validations Needed:**

**1. Configuration Validation:**
- [ ] Required fields present (model name, graph, schema)
- [ ] Valid YAML syntax
- [ ] No duplicate node IDs
- [ ] No duplicate edge definitions
- [ ] All referenced tables exist in schema

**2. Graph Validation:**
- [ ] All edges reference existing nodes
- [ ] No circular dependencies in paths
- [ ] Foreign keys match between tables
- [ ] All path hops reference existing nodes
- [ ] Graph is connected (no orphaned nodes)

**3. Data Validation:**
- [ ] Bronze tables exist before building
- [ ] Column names match config
- [ ] Join keys exist in both tables
- [ ] Data types are compatible

**4. Performance Validation:**
- [ ] Warn about large Cartesian products
- [ ] Warn about missing indexes
- [ ] Suggest partitioning strategies

**Implementation:**
```python
class ModelValidator:
    def validate_config(self, model_cfg: dict) -> List[ValidationError]:
        """Validate YAML configuration."""
        pass

    def validate_graph(self, nodes: list, edges: list) -> List[ValidationError]:
        """Validate graph structure."""
        pass

    def validate_data(self, model: BaseModel) -> List[ValidationError]:
        """Validate data before building."""
        pass
```

**Usage:**
```python
validator = ModelValidator()
errors = validator.validate_all(model)
if errors:
    raise ModelValidationError(errors)
model.build()
```

---

#### MOD-CORE-003: Add Logging Framework
**Status:** Not Started
**Priority:** High
**Effort:** 3-5 days

**Description:**
Structured logging throughout model building and querying.

**Logging Levels:**
- **DEBUG:** Detailed query plans, transformation steps
- **INFO:** Model building progress, table counts
- **WARNING:** Performance issues, missing data
- **ERROR:** Build failures, validation errors

**Features:**
- [ ] Configurable log levels
- [ ] Structured JSON logging for production
- [ ] Pretty console output for development
- [ ] Timing information for operations
- [ ] Context (model name, table name, operation)

**Example:**
```python
import logging
logger = logging.getLogger('defunk.models.company')

logger.info("Building company model", extra={
    'model': 'company',
    'operation': 'build',
    'node_count': 10,
    'edge_count': 5
})
```

---

### High Priority

#### MOD-CORE-004: Support Delta/Append Write Modes
**Status:** Not Started
**Priority:** High
**Effort:** 5-7 days

**Description:**
Currently `write_tables()` only supports overwrite mode. Add support for incremental writes.

**Write Modes to Support:**
- [x] **overwrite** - Replace all data (current)
- [ ] **append** - Add new data (no dedup)
- [ ] **merge** - Upsert based on primary key
- [ ] **incremental** - Only new records (watermark-based)

**Configuration:**
```yaml
# Model config
storage:
  write_mode: merge
  merge_key: [ticker, trade_date]
  watermark_column: trade_date
```

**Usage:**
```python
# Append mode
model.write_tables(mode='append')

# Merge mode (upsert)
model.write_tables(
    mode='merge',
    merge_keys={'fact_prices': ['ticker', 'trade_date']}
)

# Incremental mode
model.write_tables(
    mode='incremental',
    watermark='2024-01-01'
)
```

**Implementation:**
- Use Delta Lake for merge operations
- Track watermarks in metadata table
- Add conflict resolution strategies

---

#### MOD-CORE-005: Implement Caching for Measures
**Status:** Not Started
**Priority:** High
**Effort:** 3-5 days

**Description:**
Cache expensive measure calculations to avoid recomputation.

**Caching Strategy:**
- [ ] In-memory cache for session
- [ ] Persistent cache to disk
- [ ] Cache invalidation on data change
- [ ] Configurable cache TTL

**Features:**
- [ ] Cache key based on measure name + filters
- [ ] LRU eviction policy
- [ ] Cache hit/miss statistics
- [ ] Option to disable caching

**Implementation:**
```python
from functools import lru_cache
import hashlib

class BaseModel:
    def calculate_measure(self, measure_name, filters=None):
        cache_key = self._measure_cache_key(measure_name, filters)

        if cache_key in self._measure_cache:
            logger.debug(f"Cache hit for {measure_name}")
            return self._measure_cache[cache_key]

        result = self._calculate_measure_impl(measure_name, filters)
        self._measure_cache[cache_key] = result
        return result
```

---

#### MOD-CORE-006: Add SQL Query Interface
**Status:** Not Started
**Priority:** High
**Effort:** 5-7 days

**Description:**
Allow users to run custom SQL queries against model tables.

**Features:**
- [ ] Execute arbitrary SQL
- [ ] Access all model tables
- [ ] Use Spark SQL or DuckDB SQL
- [ ] Return results as DataFrame or Pandas
- [ ] Query validation and sanitization

**Usage:**
```python
# Via model
result = company_model.query("""
    SELECT ticker, AVG(close) as avg_price
    FROM fact_prices
    WHERE trade_date >= '2024-01-01'
    GROUP BY ticker
    ORDER BY avg_price DESC
    LIMIT 10
""")

# Via session (cross-model queries)
result = session.query("""
    SELECT
        c.ticker,
        c.avg_price,
        m.unemployment_rate
    FROM company.fact_prices c
    JOIN macro.fact_employment m
        ON c.trade_date = m.report_date
""")
```

**Security:**
- Read-only queries only
- No DDL operations allowed
- Query timeouts
- Resource limits

---

### Medium Priority

#### MOD-CORE-007: Support Custom UDFs in Transforms
**Status:** Not Started
**Priority:** Medium
**Effort:** 5-7 days

**Description:**
Allow users to define custom transformation functions in Python.

**Configuration:**
```yaml
graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker
      transforms:
        - select: ["ticker", "name"]
        - custom_udf:
            function: mypackage.transforms.clean_ticker
            inputs: [ticker]
            output: ticker_clean
```

**Python UDF:**
```python
# mypackage/transforms.py
from pyspark.sql import Column
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

@udf(returnType=StringType())
def clean_ticker(ticker: str) -> str:
    """Remove special characters from ticker."""
    return ticker.replace('.', '').replace('-', '').upper()
```

**Features:**
- [ ] Register UDFs from Python modules
- [ ] Type checking for UDF inputs/outputs
- [ ] Error handling for UDF failures
- [ ] Support vectorized UDFs (Pandas UDF)

---

#### MOD-CORE-008: Implement Slowly-Changing Dimensions (SCD)
**Status:** Not Started
**Priority:** Medium
**Effort:** 1-2 weeks

**Description:**
Support tracking historical changes to dimension attributes.

**SCD Types:**
- [ ] **Type 1:** Overwrite (current behavior)
- [ ] **Type 2:** Add new row with version
- [ ] **Type 3:** Add new column for previous value
- [ ] **Type 4:** Separate history table

**Configuration:**
```yaml
schema:
  dimensions:
    dim_company:
      path: dims/dim_company
      scd_type: 2
      scd_columns: [company_name, exchange_code]
      natural_key: [ticker]
      version_columns:
        valid_from: date
        valid_to: date
        is_current: boolean
```

**Example:**
```
ticker | company_name | valid_from | valid_to   | is_current
-------|--------------|------------|------------|------------
AAPL   | Apple Inc    | 1980-12-12 | 2007-01-09 | false
AAPL   | Apple Inc.   | 2007-01-09 | 9999-12-31 | true
```

---

## Model Features

### High Priority

#### MOD-FEAT-001: Cross-Model Joins
**Status:** Not Started
**Priority:** High
**Effort:** 1-2 weeks

**Description:**
Enable joining tables from different models.

**Use Cases:**
- Join company prices with macro indicators
- Join city finance with economic data
- Combine multiple fact tables

**Configuration:**
```yaml
# In model config
cross_model_paths:
  - id: prices_with_macro
    description: Stock prices enriched with macro indicators
    joins:
      - model: company
        table: fact_prices
        key: trade_date
      - model: macro
        table: fact_employment
        key: report_date
    select:
      - company.ticker
      - company.close
      - macro.unemployment_rate
```

**Implementation:**
```python
# Via session
session.cross_model_query(
    models=['company', 'macro'],
    joins=[
        ('company.fact_prices', 'macro.fact_employment', 'trade_date', 'report_date')
    ]
)
```

**Challenges:**
- Different storage locations
- Schema evolution across models
- Performance optimization

---

#### MOD-FEAT-002: Model Versioning
**Status:** Not Started
**Priority:** High
**Effort:** 1-2 weeks

**Description:**
Support multiple versions of a model running side-by-side.

**Use Cases:**
- Test schema changes without breaking production
- A/B testing of transformations
- Gradual migration to new model structure

**Configuration:**
```yaml
# configs/models/company.yaml
version: 2.0
schema_version: 2024-11-01

# Storage paths include version
storage:
  root: storage/silver/company/v2
```

**API:**
```python
# Load specific version
company_v1 = session.load_model('company', version='1.0')
company_v2 = session.load_model('company', version='2.0')

# Compare results
diff = ModelComparator.compare(company_v1, company_v2, table='fact_prices')
```

**Features:**
- [ ] Version detection from config
- [ ] Separate storage per version
- [ ] Schema comparison tools
- [ ] Migration utilities

---

#### MOD-FEAT-003: Model Dependencies and DAG
**Status:** Not Started
**Priority:** High
**Effort:** 1 week

**Description:**
Explicit model dependencies and build orchestration.

**Configuration:**
```yaml
# configs/models/forecast.yaml
depends_on:
  - company  # Requires company model to be built first
  - macro    # Requires macro model to be built first
```

**Features:**
- [ ] Automatic dependency resolution
- [ ] Topological sort for build order
- [ ] Parallel builds where possible
- [ ] Dependency cycle detection
- [ ] Visualize dependency graph

**Implementation:**
```python
# Build all models in dependency order
session.build_all_models(parallel=True)

# Visualize dependency graph
session.show_dependency_graph()
```

---

### Medium Priority

#### MOD-FEAT-004: Model Metadata and Documentation
**Status:** Not Started
**Priority:** Medium
**Effort:** 3-5 days

**Description:**
Rich metadata and auto-generated documentation for models.

**Metadata to Track:**
- [ ] Model owner/author
- [ ] Created/updated timestamps
- [ ] Dependencies
- [ ] Data sources
- [ ] Table schemas
- [ ] Row counts and sizes
- [ ] Build statistics (time, records)

**Auto-Generated Docs:**
- [ ] Data dictionary (all columns)
- [ ] Relationship diagram (ERD)
- [ ] Lineage diagram (data flow)
- [ ] Usage examples
- [ ] Change log

**Output Format:**
- Markdown files
- HTML documentation site
- Interactive schema explorer

---

#### MOD-FEAT-005: Model Testing Framework
**Status:** Not Started
**Priority:** Medium
**Effort:** 1-2 weeks

**Description:**
Built-in testing framework for model validation.

**Test Types:**
- [ ] **Schema tests:** Validate column types, nullable
- [ ] **Relationship tests:** Validate foreign keys
- [ ] **Quality tests:** Check for nulls, duplicates, outliers
- [ ] **Business logic tests:** Custom validation rules

**Configuration:**
```yaml
# configs/models/company.yaml
tests:
  - table: dim_company
    tests:
      - unique: [ticker]
      - not_null: [ticker, company_name]
      - accepted_values:
          column: exchange_code
          values: [XNAS, XNYS, ARCX]

  - table: fact_prices
    tests:
      - not_null: [ticker, trade_date, close]
      - positive: [close, volume]
      - relationships:
          to: dim_company
          field: ticker
```

**Execution:**
```bash
python -m defunk test models/company
```

**Output:**
```
✅ dim_company.unique.ticker: PASSED (0 duplicates)
✅ dim_company.not_null.ticker: PASSED
❌ fact_prices.positive.volume: FAILED (5 negative values found)
```

---

## New Model Ideas

### High Interest

#### MOD-NEW-001: Portfolio Model
**Status:** Not Started
**Priority:** High
**Effort:** 2-3 weeks

**Description:**
Model for portfolio holdings, performance, and attribution.

**Tables:**
- `dim_security` - Securities (stocks, bonds, etc.)
- `dim_portfolio` - Portfolio definitions
- `fact_holdings` - Daily holdings
- `fact_transactions` - Buys/sells
- `fact_returns` - Portfolio returns
- `fact_attribution` - Performance attribution

**Measures:**
- Total return
- Risk-adjusted return (Sharpe, Sortino)
- Drawdown
- Alpha, Beta
- Sector allocation
- Attribution by security

**Dependencies:**
- Company model (for prices)
- Macro model (for benchmarks)

---

#### MOD-NEW-002: Risk Model
**Status:** Not Started
**Priority:** High
**Effort:** 2-3 weeks

**Description:**
Model for risk metrics and stress testing.

**Tables:**
- `fact_var` - Value at Risk
- `fact_stress_tests` - Scenario results
- `fact_correlations` - Asset correlations
- `fact_volatility` - Historical volatility

**Measures:**
- VaR (95%, 99%)
- Expected shortfall
- Beta to market
- Correlation matrix
- Stress test P&L

**Features:**
- Historical VaR
- Monte Carlo VaR
- Scenario analysis
- Correlation breakdown

---

#### MOD-NEW-003: Sentiment Model
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 weeks

**Description:**
Aggregate sentiment from news, social media, earnings calls.

**Tables:**
- `fact_news_sentiment` - News article sentiment
- `fact_social_sentiment` - Twitter/Reddit sentiment
- `fact_transcript_sentiment` - Earnings call sentiment
- `dim_source` - Sentiment sources

**Measures:**
- Aggregate sentiment score
- Sentiment momentum
- Sentiment divergence
- Source agreement

**Data Sources:**
- News APIs
- Twitter API
- Reddit API
- Earnings call transcripts

---

### Medium Interest

#### MOD-NEW-004: Credit Model
**Status:** Not Started
**Priority:** Medium
**Effort:** 2-3 weeks

**Description:**
Credit ratings, spreads, and default risk.

**Tables:**
- `dim_issuer` - Bond issuers
- `fact_ratings` - Credit ratings history
- `fact_spreads` - Credit spreads
- `fact_defaults` - Default events

**Measures:**
- Credit spread
- Default probability
- Recovery rate
- Rating migration

---

#### MOD-NEW-005: Commodities Model
**Status:** Not Started
**Priority:** Medium
**Effort:** 1-2 weeks

**Description:**
Commodity prices and fundamentals.

**Tables:**
- `dim_commodity` - Commodity definitions
- `fact_prices` - Spot and futures prices
- `fact_inventory` - Inventory levels
- `fact_production` - Production data

**Measures:**
- Price momentum
- Contango/backwardation
- Inventory days
- Supply/demand balance

---

#### MOD-NEW-006: Crypto Model
**Status:** Not Started
**Priority:** Medium
**Effort:** 1-2 weeks

**Description:**
Cryptocurrency prices, volumes, and on-chain metrics.

**Tables:**
- `dim_token` - Token definitions
- `fact_prices` - OHLCV data
- `fact_on_chain` - On-chain metrics
- `fact_defi` - DeFi protocol data

**Measures:**
- Market cap
- Trading volume
- On-chain volume
- Active addresses
- Total value locked (TVL)

**Data Sources:**
- CoinGecko
- CoinMarketCap
- Blockchain APIs

---

## Cross-Model Features

### High Priority

#### MOD-CROSS-001: Unified Time Dimension
**Status:** Not Started
**Priority:** High
**Effort:** 1 week

**Description:**
Shared calendar dimension across all models.

**Implementation:**
- Core model provides `dim_calendar`
- All other models join to it
- Consistent date columns across models
- Support fiscal calendars

**Benefits:**
- Consistent time-based queries
- Easy cross-model time joins
- Support for fiscal periods
- Holiday/trading day awareness

---

#### MOD-CROSS-002: Universal Measure Framework
**Status:** Not Started
**Priority:** High
**Effort:** 1-2 weeks

**Description:**
Standard measure definitions that work across models.

**Standard Measures:**
- `count` - Row count
- `sum` - Sum of column
- `avg` - Average of column
- `min`, `max` - Min/max values
- `growth_rate` - Period-over-period growth
- `moving_average` - Rolling average
- `rank` - Ranking by value

**Configuration:**
```yaml
measures:
  total_volume:
    base_measure: sum
    column: volume
    description: Total trading volume

  avg_price:
    base_measure: avg
    column: close
    description: Average closing price

  price_momentum:
    base_measure: growth_rate
    column: close
    periods: 30
    description: 30-day price change
```

---

## Model Performance

### High Priority

#### MOD-PERF-001: Query Plan Optimization
**Status:** Not Started
**Priority:** High
**Effort:** 1-2 weeks

**Description:**
Optimize query plans for common patterns.

**Optimizations:**
- [ ] Predicate pushdown
- [ ] Partition pruning
- [ ] Column pruning
- [ ] Join reordering
- [ ] Filter early, join late

**Implementation:**
- Analyze Spark query plans
- Identify optimization opportunities
- Add hints to YAML configs
- Document best practices

---

#### MOD-PERF-002: Materialized View Management
**Status:** Not Started
**Priority:** Medium
**Effort:** 1-2 weeks

**Description:**
Automatically maintain materialized views for expensive queries.

**Features:**
- [ ] Identify expensive queries
- [ ] Create materialized views
- [ ] Refresh strategies (on-demand, scheduled)
- [ ] Query rewriting to use views
- [ ] View staleness tracking

**Configuration:**
```yaml
materialized_views:
  - id: prices_monthly_summary
    source: fact_prices
    refresh: daily
    query: |
      SELECT
        DATE_TRUNC('month', trade_date) as month,
        ticker,
        AVG(close) as avg_close,
        SUM(volume) as total_volume
      FROM fact_prices
      GROUP BY month, ticker
```

---

## Success Metrics

### Model Framework
- [ ] All models use `BaseModel.write_tables()`
- [ ] 90%+ test coverage on BaseModel
- [ ] Validation catches 95% of config errors
- [ ] Build time <5 minutes for typical model

### Model Features
- [ ] Support 3+ write modes (overwrite, append, merge)
- [ ] Cross-model queries work seamlessly
- [ ] Model versioning enables safe migrations
- [ ] Measure caching improves performance 10x

### New Models
- [ ] 5+ production models by Q2 2025
- [ ] Average model creation time <2 hours
- [ ] Models documented with examples
- [ ] Tests for all models

---

## Related Documents

- [TODO Tracker](../todo-tracker.md) - All development tasks
- [Roadmap](../roadmap.md) - Product roadmap
- [Architecture TODOs](./architecture-todos.md) - Architecture improvements
- [Models Guide](../../2-models/README.md) - Model documentation
