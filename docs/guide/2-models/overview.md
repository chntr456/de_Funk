# Models Framework Overview

> **Comprehensive guide to dimensional modeling and the YAML-driven model framework in de_Funk**

This document explains the core concepts, architecture, and design patterns used in the de_Funk data modeling framework.

---

## Table of Contents

- [Dimensional Modeling Concepts](#dimensional-modeling-concepts)
- [YAML-Driven Model Framework](#yaml-driven-model-framework)
- [BaseModel Architecture](#basemodel-architecture)
- [Graph Building](#graph-building)
- [Model Lifecycle](#model-lifecycle)
- [Best Practices](#best-practices)

---

## Dimensional Modeling Concepts

### What is Dimensional Modeling?

Dimensional modeling is a data warehouse design technique optimized for querying and analysis. It organizes data into **facts** (measurements/metrics) and **dimensions** (descriptive attributes), making it intuitive for business users and efficient for analytics queries.

### Facts

**Facts** are the core measurements or metrics in your data warehouse. They typically represent:
- Transactional data (orders, trades, payments)
- Event data (clicks, views, visits)
- Periodic snapshots (daily balances, monthly totals)

**Characteristics:**
- Contain numeric measures (prices, volumes, counts, amounts)
- Often have foreign keys to dimensions
- Usually partitioned by date for query performance
- Can be large (millions to billions of rows)

**Examples in de_Funk:**
- `fact_prices` - Daily stock prices with OHLC data
- `fact_news` - News articles with sentiment scores
- `fact_unemployment` - Monthly unemployment rates
- `fact_building_permits` - Building permits with fees

```python
# Fact table structure example
fact_prices:
  trade_date: date          # Time dimension key
  ticker: string            # Company dimension key
  open: double              # Measure
  high: double              # Measure
  low: double               # Measure
  close: double             # Measure
  volume: long              # Measure
  volume_weighted: double   # Measure
```

### Dimensions

**Dimensions** provide the descriptive context for facts. They answer the "who, what, where, when, why" questions about your data.

**Characteristics:**
- Contain descriptive attributes (names, descriptions, categories)
- Usually have a primary key
- Relatively small (hundreds to thousands of rows)
- Slowly changing (updated infrequently)

**Examples in de_Funk:**
- `dim_company` - Company information (ticker, name, exchange)
- `dim_calendar` - Date attributes (year, quarter, month, weekday flags)
- `dim_exchange` - Stock exchange reference data
- `dim_community_area` - Chicago community area geographies

```python
# Dimension table structure example
dim_company:
  ticker: string            # Primary key
  company_name: string      # Descriptive attribute
  exchange_code: string     # Foreign key to dim_exchange
  company_id: string        # Surrogate key
  market_cap_proxy: double  # Attribute
  latest_trade_date: date   # Attribute
```

### Measures

**Measures** are pre-defined calculations and aggregations that operate on fact tables. They encapsulate business logic for consistent metrics across the organization.

**Types:**
1. **Simple Measures** - Direct aggregations (avg, sum, min, max, count)
2. **Computed Measures** - Calculations involving multiple columns
3. **Weighted Measures** - Aggregations with weighting schemes

**Examples:**
```yaml
# Simple measure
avg_close_price:
  source: fact_prices.close
  aggregation: avg
  data_type: double
  format: "$#,##0.00"

# Computed measure
market_cap:
  type: computed
  source: fact_prices.close
  expression: "close * volume"
  aggregation: avg
  data_type: double
  format: "$#,##0.00"

# Weighted measure
market_cap_weighted_index:
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: market_cap
  group_by: [trade_date]
  data_type: double
```

### Star Schema

The **star schema** is a dimensional modeling pattern where:
- Facts sit at the center
- Dimensions radiate outward like points on a star
- Joins are simple (fact to dimension)
- Queries are fast and intuitive

```
                    dim_calendar
                         |
                         |
    dim_exchange --- dim_company --- fact_prices --- fact_news
                         |
                         |
                    dim_exchange
```

---

## YAML-Driven Model Framework

### Philosophy

The de_Funk model framework is **declarative and configuration-driven**. Models are defined in YAML files that serve as the **single source of truth** for:
- Schema definitions (tables, columns, data types)
- Graph structure (nodes, edges, paths)
- Measures (calculations and aggregations)
- Data sources (Bronze layer mappings)
- Dependencies (model relationships)

This approach provides:
- **Version control** - Track model changes in git
- **Documentation** - YAML serves as living documentation
- **Validation** - Schema enforcement and consistency checks
- **Code generation** - Models build themselves from config
- **Portability** - Easy to migrate between engines (Spark, DuckDB)

### YAML Structure

Every model has a YAML configuration file in `/configs/models/<model_name>.yaml`:

```yaml
version: 1
model: company
tags: [equities, polygon, us]
description: "Financial market and company data"

# Dependencies on other models
depends_on:
  - core  # Uses shared dim_calendar

# Storage configuration
storage:
  root: storage/silver/company
  format: parquet

# Schema definitions
schema:
  dimensions:
    dim_company:
      path: dims/dim_company
      description: "Company dimension"
      columns:
        ticker: string
        company_name: string
      primary_key: [ticker]
      tags: [dim, entity]

  facts:
    fact_prices:
      path: facts/fact_prices
      description: "Daily stock prices"
      columns:
        trade_date: date
        ticker: string
        close: double
      partitions: [trade_date]
      tags: [fact, prices]

# Measures
measures:
  avg_close_price:
    source: fact_prices.close
    aggregation: avg
    data_type: double

# Graph structure
graph:
  nodes:
    - id: dim_company
      from: bronze.ref_ticker
      select:
        ticker: ticker
        company_name: name

  edges:
    - from: fact_prices
      to: dim_company
      on: ["ticker=ticker"]
      type: many_to_one
```

### Configuration Sections

#### 1. Metadata
```yaml
version: 1
model: company
tags: [equities, polygon, us]
description: "Financial market and company data"
depends_on: [core]
```

#### 2. Storage
```yaml
storage:
  root: storage/silver/company
  format: parquet
```

#### 3. Schema
Defines all tables (dimensions and facts) with:
- Path (storage location)
- Description (documentation)
- Columns (name and type)
- Primary keys
- Partitioning strategy
- Tags (metadata)

#### 4. Measures
Pre-defined calculations with:
- Source (table.column)
- Aggregation type (avg, sum, max, etc.)
- Data type
- Formatting
- Tags

#### 5. Graph
Defines relationships as a graph:
- **Nodes** - Tables loaded from Bronze
- **Edges** - Foreign key relationships
- **Paths** - Materialized joins (views)

---

## BaseModel Architecture

### Overview

All models in de_Funk inherit from `BaseModel`, a generic class that implements:
- YAML config parsing
- Graph building from configuration
- Node loading from Bronze layer
- Edge validation
- Path materialization
- Table access methods
- Measure calculations
- Backend abstraction (Spark, DuckDB)

**File:** `/home/user/de_Funk/models/base/model.py`

### Key Features

#### 1. Generic Graph Building
The `build()` method implements a standard build process for all models:

```python
def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
    """
    Steps:
    1. Build nodes from schema (read Bronze, apply transformations)
    2. Validate edges (ensure join paths exist)
    3. Materialize paths (create joined views)
    4. Separate into dims and facts
    """
    self.before_build()  # Hook for custom pre-processing

    nodes = self._build_nodes()
    self._apply_edges(nodes)
    paths = self._materialize_paths(nodes)

    dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
    facts = {**{k: v for k, v in nodes.items() if k.startswith("fact_")}, **paths}

    dims, facts = self.after_build(dims, facts)  # Hook for custom post-processing

    return dims, facts
```

#### 2. Node Loading
Nodes are loaded from the Bronze layer with transformations:

```python
def _build_nodes(self) -> Dict[str, DataFrame]:
    """
    For each node:
    1. Load from Bronze (via custom loading or default)
    2. Apply select transformations (column mapping)
    3. Apply derive transformations (computed columns)
    """
    for node_config in self.model_cfg['graph']['nodes']:
        node_id = node_config['id']

        # Load from Bronze
        layer, table = node_config['from'].split('.', 1)
        df = self._load_bronze_table(table)

        # Apply column selection/aliasing
        if 'select' in node_config:
            df = self._select_columns(df, node_config['select'])

        # Apply computed columns
        if 'derive' in node_config:
            for col_name, expr in node_config['derive'].items():
                df = self._apply_derive(df, col_name, expr, node_id)

        nodes[node_id] = df
```

#### 3. Edge Validation
Validates that joins are possible between tables:

```python
def _apply_edges(self, nodes: Dict[str, DataFrame]) -> None:
    """
    Validate edges with dry-run joins:
    - Both nodes exist
    - Join columns exist
    - Join is valid
    """
    for edge in self.model_cfg['graph']['edges']:
        left = nodes[edge['from']]
        right = nodes[edge['to']]

        # Get join keys
        pairs = self._join_pairs_from_strings(edge['on'])

        # Dry-run validation
        _ = left.limit(1).join(
            right.limit(1),
            on=[left[l] == right[r] for l, r in pairs],
            how='left'
        )
```

#### 4. Path Materialization
Creates materialized views by joining nodes:

```python
def _materialize_paths(self, nodes: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
    """
    Materialize path definitions by joining nodes.

    Example path:
      hops: "fact_prices -> dim_company -> dim_exchange"

    Results in:
      prices_with_company_and_exchange (fully denormalized view)
    """
    for path_config in self.model_cfg['graph']['paths']:
        chain = path_config['hops'].split('->')

        df = nodes[chain[0]]

        for i in range(len(chain) - 1):
            left_id = chain[i]
            right_id = chain[i + 1]
            right_df = nodes[right_id]

            # Find join keys from edge definition
            edge = self._find_edge(left_id, right_id)
            pairs = self._join_pairs_from_strings(edge['on'])

            # Join with deduplication
            df = self._join_with_dedupe(df, right_df, pairs, how='left')

        paths[path_config['id']] = df
```

#### 5. Measure Calculations
Generic measure calculation from YAML config:

```python
def calculate_measure_by_entity(
    self,
    measure_name: str,
    entity_column: str,
    limit: Optional[int] = None
) -> DataFrame:
    """
    Calculate a measure aggregated by entity.
    Reads measure definitions from YAML config.

    Example:
        df = model.calculate_measure_by_entity('market_cap', 'ticker', limit=10)
        # Returns: DataFrame with [ticker, market_cap]
    """
    measure_config = self.model_cfg['measures'][measure_name]
    table_name, column_name = measure_config['source'].split('.')
    aggregation = measure_config['aggregation']

    source_table = self.get_table(table_name)

    result = (
        source_table
        .groupBy(entity_column)
        .agg(getattr(F, aggregation)(F.col(column_name)).alias(measure_name))
        .orderBy(F.desc(measure_name))
    )

    if limit:
        result = result.limit(limit)

    return result
```

#### 6. Backend Abstraction
Supports multiple execution engines:

```python
def _detect_backend(self) -> str:
    """Detect backend type from connection."""
    connection_type = str(type(self.connection))

    if 'spark' in connection_type.lower():
        return 'spark'
    elif 'duckdb' in connection_type.lower():
        return 'duckdb'
    else:
        raise ValueError(f"Unknown connection type: {connection_type}")
```

### Extension Points

Models can override these hooks for customization:

```python
def before_build(self):
    """Called before build() - for custom pre-processing"""
    pass

def after_build(self, dims, facts):
    """Called after build() - for custom post-processing"""
    return dims, facts

def custom_node_loading(self, node_id, node_config):
    """Override to customize node loading"""
    return None  # Return None to use default loading
```

### Table Access Methods

BaseModel provides intuitive table access:

```python
# Get any table
df = model.get_table('fact_prices')

# Get dimension specifically
companies = model.get_dimension_df('dim_company')

# Get fact specifically
prices = model.get_fact_df('fact_prices')

# List all tables
tables = model.list_tables()
# Returns: {'dimensions': ['dim_company', ...], 'facts': ['fact_prices', ...]}
```

---

## Graph Building

### Nodes, Edges, and Paths

The graph-based model structure provides a clear, visual way to understand data relationships.

#### Nodes

**Nodes** represent tables (dimensions and facts) loaded from the Bronze layer.

```yaml
nodes:
  - id: dim_company
    from: bronze.ref_ticker        # Source table
    select:                         # Column mappings
      ticker: ticker
      company_name: name
      exchange_code: exchange_code
    derive:                         # Computed columns
      company_id: "sha1(ticker)"
    tags: [dim, entity]
    unique_key: [ticker]
```

**Node Loading Process:**
1. Load from Bronze layer using `from` specification
2. Apply `select` transformations (column aliasing)
3. Apply `derive` transformations (computed columns)
4. Tag for metadata and categorization

**Supported Derive Expressions:**
- Column references: `"ticker"` → `F.col("ticker")`
- SHA1 hash: `"sha1(ticker)"` → `F.sha1(F.col("ticker"))`
- Direct SQL expressions (DuckDB backend)

#### Edges

**Edges** define relationships between nodes (foreign key constraints).

```yaml
edges:
  - from: fact_prices
    to: dim_company
    on: ["ticker=ticker"]
    type: many_to_one
    description: "Prices belong to a company"

  - from: dim_company
    to: dim_exchange
    on: ["exchange_code=exchange_code"]
    type: many_to_one
    description: "Company lists on an exchange"
```

**Edge Types:**
- `many_to_one` - Many facts to one dimension (most common)
- `one_to_many` - One dimension to many facts
- `one_to_one` - Direct relationship
- `many_to_many` - Bridge table relationship

**Edge Validation:**
The framework validates edges during build:
- Both nodes exist
- Join columns exist in both tables
- Join is valid (dry-run with `limit(1)`)

#### Paths

**Paths** represent materialized joins (analytics-ready views).

```yaml
paths:
  - id: prices_with_company
    hops: "fact_prices -> dim_company -> dim_exchange"
    description: "Prices with full company and exchange context"
    tags: [canonical, analytics]
```

**Path Materialization:**
1. Start with base fact table
2. Join each dimension in sequence
3. Deduplicate columns (avoid ambiguity)
4. Create denormalized view

**Example:**
```
fact_prices:                        prices_with_company:
  - trade_date                        - trade_date
  - ticker                            - ticker
  - close                             - close
  - volume                            - volume
  +                                   - company_name
dim_company:                          - exchange_code
  - ticker                            - exchange_name
  - company_name         →            - market_cap_proxy
  - exchange_code
  +
dim_exchange:
  - exchange_code
  - exchange_name
```

### Graph Visualization

#### ASCII Diagram Format

```
┌─────────────────┐
│  dim_exchange   │
│  (Exchange Ref) │
└────────┬────────┘
         │
         │ exchange_code
         │
┌────────▼────────┐         ┌──────────────────┐
│  dim_company    │◄────────│  fact_prices     │
│  (Companies)    │ ticker  │  (Daily Prices)  │
└─────────────────┘         └──────────────────┘
         │
         │ ticker
         │
┌────────▼────────┐
│   fact_news     │
│  (News Articles)│
└─────────────────┘

Legend:
  ┌─────┐
  │     │  = Table (node)
  └─────┘

  ──▶    = Relationship (edge)

  label  = Join column
```

### Graph Benefits

1. **Visual Understanding** - Easy to see relationships
2. **Query Optimization** - Framework knows optimal join paths
3. **Materialized Views** - Pre-computed joins for fast queries
4. **Graph Databases** - Ready for Neo4j, Neptune, etc.
5. **Metadata** - Self-documenting data model

---

## Model Lifecycle

### 1. Definition Phase

**Create YAML configuration:**

```bash
# Create new model config
touch configs/models/my_model.yaml
```

**Define schema, graph, and measures:**

```yaml
version: 1
model: my_model
tags: [domain, source]
description: "My custom data model"

depends_on: [core]

storage:
  root: storage/silver/my_model
  format: parquet

schema:
  dimensions:
    dim_entity:
      path: dims/dim_entity
      columns:
        entity_id: string
        entity_name: string
      primary_key: [entity_id]

  facts:
    fact_metrics:
      path: facts/fact_metrics
      columns:
        date: date
        entity_id: string
        value: double
      partitions: [date]

graph:
  nodes:
    - id: dim_entity
      from: bronze.entities
      select:
        entity_id: id
        entity_name: name

    - id: fact_metrics
      from: bronze.metrics
      select:
        date: date
        entity_id: entity_id
        value: value

  edges:
    - from: fact_metrics
      to: dim_entity
      on: ["entity_id=entity_id"]

measures:
  avg_value:
    source: fact_metrics.value
    aggregation: avg
    data_type: double
```

### 2. Implementation Phase

**Create Python model class:**

```python
# models/implemented/my_model/model.py
from models.base.model import BaseModel

class MyModel(BaseModel):
    """
    My custom model.

    Inherits all functionality from BaseModel.
    YAML config drives everything.
    """

    # Override hooks if needed
    def before_build(self):
        """Custom pre-processing"""
        print("Building my model...")

    def after_build(self, dims, facts):
        """Custom post-processing"""
        # Add custom transformations if needed
        return dims, facts
```

**Register in registry:**

```python
# models/registry.py
from models.implemented.my_model.model import MyModel

MODEL_REGISTRY = {
    'core': CoreModel,
    'company': CompanyModel,
    'my_model': MyModel,  # Add your model
}
```

### 3. Build Phase

**Initialize and build:**

```python
from core.context import RepoContext
from models.api.session import UniversalSession

# Initialize session
ctx = RepoContext.from_repo_root()
session = UniversalSession(ctx.connection, ctx.config_root, ctx.storage_cfg)

# Load model
my_model = session.load_model('my_model')

# Build (loads from Bronze, applies transformations)
dims, facts = my_model.build()

# Inspect
print(f"Dimensions: {list(dims.keys())}")
print(f"Facts: {list(facts.keys())}")
```

### 4. Validation Phase

**Validate schema and data:**

```python
# Check tables were created
tables = my_model.list_tables()
print(tables)

# Check dimension
dim_entity = my_model.get_dimension_df('dim_entity')
print(f"Entities: {dim_entity.count()}")
dim_entity.show(5)

# Check fact
fact_metrics = my_model.get_fact_df('fact_metrics')
print(f"Metrics: {fact_metrics.count()}")
fact_metrics.show(5)

# Validate edges
relations = my_model.get_relations()
print(f"Relationships: {relations}")

# Calculate measures
top_entities = my_model.calculate_measure_by_entity('avg_value', 'entity_id', limit=10)
top_entities.show()
```

### 5. Persistence Phase

**Write to Silver layer:**

```python
# Write all tables to storage
stats = my_model.write_tables(
    output_root="storage/silver/my_model",
    format="parquet",
    mode="overwrite",
    partition_by={
        "fact_metrics": ["date"]
    }
)

print(f"Wrote {stats['total_tables']} tables")
print(f"Total rows: {stats['total_rows']:,}")
```

### 6. Usage Phase

**Query and analyze:**

```python
# Load from session
my_model = session.load_model('my_model')

# Get tables
entities = session.get_table('my_model', 'dim_entity')
metrics = session.get_table('my_model', 'fact_metrics')

# Apply filters
filtered_metrics = my_model.get_fact_df('fact_metrics')
filtered_metrics = filtered_metrics.filter(
    (F.col('date') >= '2024-01-01') &
    (F.col('date') <= '2024-12-31')
)

# Calculate measures
results = my_model.calculate_measure_by_entity('avg_value', 'entity_id', limit=20)
results.toPandas()  # Convert to pandas for analysis
```

---

## Best Practices

### 1. Model Design

#### Start with Business Questions
Design models to answer specific business questions:
- What are we trying to measure?
- How do we slice the data?
- What calculations do we need?

#### Use Star Schema
Keep it simple with star schema:
- Facts at center
- Dimensions radiating outward
- Avoid snowflaking unless necessary

#### Denormalize for Performance
Create materialized paths for common queries:
```yaml
paths:
  - id: prices_with_company
    hops: "fact_prices -> dim_company -> dim_exchange"
    tags: [canonical, analytics]
```

#### Partition Large Tables
Always partition facts by date:
```yaml
fact_prices:
  partitions: [trade_date]

fact_unemployment:
  partitions: [year]
```

### 2. Schema Design

#### Use Consistent Naming
- Dimensions: `dim_<entity>` (dim_company, dim_calendar)
- Facts: `fact_<event>` (fact_prices, fact_unemployment)
- Measures: `<agg>_<metric>` (avg_close_price, total_volume)

#### Document Everything
```yaml
dim_company:
  description: "Company dimension with ticker, exchange info, and market cap"
  columns:
    ticker: string            # Primary key
    company_name: string      # Official company name
    exchange_code: string     # Stock exchange (NYSE, NASDAQ, etc.)
```

#### Choose Appropriate Data Types
- Use `date` for dates, not strings
- Use `long` for large integers (volumes, counts)
- Use `double` for decimals (prices, rates)

### 3. Graph Design

#### Define Explicit Edges
Don't rely on inference - be explicit:
```yaml
edges:
  - from: fact_prices
    to: dim_company
    on: ["ticker=ticker"]
    type: many_to_one
    description: "Prices belong to a company"
```

#### Create Paths for Common Joins
Pre-materialize frequently used joins:
```yaml
paths:
  - id: prices_with_company
    hops: "fact_prices -> dim_company -> dim_exchange"
    description: "Prices with full company and exchange context"
```

#### Use Tags for Organization
```yaml
tags: [canonical, analytics, materialized]
```

### 4. Measure Design

#### Pre-Define Common Metrics
Create reusable measures in YAML:
```yaml
measures:
  market_cap:
    description: "Market capitalization proxy (close * volume)"
    type: computed
    source: fact_prices.close
    expression: "close * volume"
    aggregation: avg
```

#### Use Weighted Aggregates
For multi-entity indices:
```yaml
market_cap_weighted_index:
  type: weighted_aggregate
  source: fact_prices.close
  weighting_method: market_cap
  group_by: [trade_date]
```

### 5. Dependencies

#### Minimize Dependencies
Only depend on what you need:
```yaml
depends_on:
  - core  # All models need calendar
```

#### Document Why
```yaml
depends_on:
  - core     # Uses shared dim_calendar for time-based queries
  - company  # Forecast model reads from company for training data
```

### 6. Performance

#### Lazy Loading
Models use lazy loading - tables only built when accessed:
```python
model.ensure_built()  # Triggers build if not already built
```

#### Optimized Writers
Use ParquetLoader for better write performance:
```python
stats = model.write_tables(
    use_optimized_writer=True,  # Default
    partition_by={"fact_prices": ["trade_date"]}
)
```

#### Limit Preview Queries
When exploring, always limit:
```python
df.show(10)  # Not df.show()
df.limit(1000).toPandas()  # Not df.toPandas()
```

### 7. Testing

#### Validate Schema
```python
# Check all tables exist
tables = model.list_tables()
assert 'dim_company' in tables['dimensions']
assert 'fact_prices' in tables['facts']

# Check columns
df = model.get_table('fact_prices')
assert 'trade_date' in df.columns
assert 'ticker' in df.columns
```

#### Test Measures
```python
# Calculate measure
result = model.calculate_measure_by_entity('avg_close_price', 'ticker', limit=10)

# Validate
assert result.count() <= 10
assert 'ticker' in result.columns
assert 'avg_close_price' in result.columns
```

#### Validate Relationships
```python
# Check edges
relations = model.get_relations()
assert 'fact_prices' in relations
assert 'dim_company' in relations['fact_prices']
```

### 8. Documentation

#### YAML is Documentation
Treat YAML configs as living documentation:
```yaml
fact_prices:
  description: "Daily stock prices from Polygon API"
  columns:
    trade_date: date          # Trading date (YYYY-MM-DD)
    ticker: string            # Stock ticker symbol (AAPL, GOOGL, etc.)
    close: double             # Closing price in USD
```

#### Create Model Guides
Document each model thoroughly:
- Overview and purpose
- Schema definitions
- Data sources
- Graph structure
- Usage examples
- Update frequency

#### Keep README Updated
Update model counts and stats:
```markdown
**Last Updated:** 2024-11-08
**Total Models:** 5
**Total Tables:** 18 (5 dimensions, 11 facts, 2 materialized views)
```

---

## Summary

The de_Funk model framework provides a powerful, flexible foundation for dimensional modeling:

- **Declarative** - Models defined in YAML, not code
- **Generic** - BaseModel handles all common logic
- **Extensible** - Override hooks for customization
- **Validated** - Schema enforcement and consistency checks
- **Performant** - Lazy loading, optimized writes, partitioning
- **Portable** - Backend abstraction (Spark, DuckDB)

By following these patterns and best practices, you can create robust, maintainable data models that scale from prototypes to production.

---

**Next Steps:**
- See [Core Model](implemented/core-model.md) for the foundation model
- See [Company Model](implemented/company-model.md) for a full-featured example
- See [How to Create a Model](../1-getting-started/how-to/create-a-model.md) for step-by-step guide

---

**Related Documentation:**
- [Models System Architecture](../3-architecture/components/models-system/overview.md)
- [Bronze Layer](../3-architecture/layers/bronze.md)
- [Silver Layer](../3-architecture/layers/silver.md)
- [UniversalSession API](../4-api-reference/universal-session.md)
