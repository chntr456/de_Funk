# Glossary

**Key terms and concepts in de_Funk**

---

## A

### Asset Type
Classification of financial instruments. Values: `stocks`, `options`, `etfs`, `futures`.

Used for partitioning Bronze tables and filtering in Silver models.

---

## B

### Backend
The database engine used for queries. Supported: **DuckDB** (primary), **Spark** (optional).

### BaseModel
Foundation class for all dimensional models (`models/base/model.py`). Provides 40+ methods for graph building, data access, and measure execution.

### Bronze Layer
First storage layer containing raw, normalized API data. Located at `storage/bronze/`.

**Characteristics**:
- Partitioned Parquet files
- Facet-normalized schema
- No transformations beyond normalization

---

## C

### CIK (Central Index Key)
SEC's permanent 10-digit identifier for companies. Used to link stocks to company entities.

Example: Apple Inc. = `0000320193`

### Computed Measure
Measure calculated from an expression on existing columns.

```yaml
computed_measures:
  price_range:
    expression: "high - low"
    source_table: fact_stock_prices
```

### ConfigLoader
Centralized configuration loading system (`config/loader.py`). Handles precedence: env vars > params > files > defaults.

### Cross-Model Reference
Accessing tables from another model within a graph definition.

```yaml
edges:
  - from: fact_stock_prices
    to: core.dim_calendar  # Cross-model reference
    on: [trade_date = date]
```

---

## D

### DAG (Directed Acyclic Graph)
Graph structure used for model dependencies and table relationships. Enables topological sorting for build order.

### Derive
YAML operation to create computed columns from expressions.

```yaml
derive:
  equity_key: sha1(ticker)
  price_range: high - low
```

### Dimension
Reference/lookup table in a star schema. Prefixed with `dim_`.

Examples: `dim_calendar`, `dim_stock`, `dim_company`

### DuckDB
High-performance analytics database. Primary backend for de_Funk. 10-100x faster than Spark for analytics queries.

---

## E

### Edge
Relationship between two nodes (tables) in a model graph.

```yaml
edges:
  - from: fact_stock_prices
    to: dim_stock
    on: [ticker = ticker]
```

### Exhibit
Visualization component in a notebook.

```markdown
$exhibits${
  "type": "line_chart",
  "data": "query_result",
  "x": "date",
  "y": "close_price"
}
```

### Extends (YAML)
Keyword for component-level inheritance in YAML configurations.

```yaml
extends: _base.securities.schema
```

---

## F

### Facet
Data transformation component that normalizes API responses to standard schemas.

Examples: `SecuritiesReferenceFacetAV`, `UnemploymentFacet`

### Fact
Measurable event table in a star schema. Prefixed with `fact_`.

Examples: `fact_stock_prices`, `fact_forecasts`, `fact_unemployment`

### Filter
Condition applied to queries or data access.

```python
filters = [{"column": "ticker", "operator": "=", "value": "AAPL"}]
```

### Filter Context
Folder-level filter configuration in notebooks (`.filter_context.yaml`).

---

## G

### Graph
Structure of nodes (tables) and edges (relationships) defining a dimensional model.

### Graph Building
Process of creating dimensional tables from Bronze data using YAML configuration.

---

## H

### Hop
Step in a path definition connecting nodes.

```yaml
paths:
  - id: prices_with_company
    hops: fact_stock_prices -> dim_stock -> company.dim_company
```

---

## I

### Ingestor
Orchestration component that fetches data from APIs and writes to Bronze.

Examples: `AlphaVantageIngestor`, `BLSIngestor`

### Inherits From (YAML)
Keyword for model-level inheritance.

```yaml
inherits_from: _base.securities
```

---

## L

### Lazy Loading
Pattern where tables are built only on first access.

```python
model.ensure_built()  # Builds only if not already built
```

---

## M

### Measure
Pre-defined calculation on model data. Types: simple, computed, weighted, Python.

### MeasureExecutor
Component that calculates measures with filter and grouping support.

### ModelConfigLoader
YAML loader with inheritance resolution for modular model configurations.

---

## N

### Node
Table definition in a model graph.

```yaml
nodes:
  - id: dim_stock
    from: bronze.securities_reference
    filters: ["asset_type = 'stocks'"]
```

### Notebook
Markdown document with interactive filters and exhibits.

---

## O

### OHLCV
Standard price data format: Open, High, Low, Close, Volume.

---

## P

### Parquet
Columnar file format used for all data storage in de_Funk.

### Path
Materialized join across multiple nodes.

```yaml
paths:
  - id: prices_with_calendar
    hops: fact_prices -> dim_calendar
```

### Provider
API-specific client handling authentication, rate limiting, and HTTP requests.

### Python Measure
Complex measure implemented in Python rather than YAML.

```yaml
python_measures:
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
```

---

## Q

### Query Planner
Component that resolves cross-model joins and optimizes query execution.

---

## R

### Rate Limiting
API call frequency control to avoid exceeding provider limits.

### Registry
Collection of available models or providers.

---

## S

### Select
YAML operation to choose and rename columns.

```yaml
select:
  ticker: ticker
  company_name: name
  exchange: primary_exchange
```

### Session
Query interface for accessing model data. See `UniversalSession`.

### Silver Layer
Second storage layer containing dimensional models. Located at `storage/silver/`.

**Characteristics**:
- Star/snowflake schemas
- YAML-configured transformations
- Ready for analytics

### Simple Measure
Direct aggregation on a single column.

```yaml
simple_measures:
  avg_close_price:
    source: fact_stock_prices.close
    aggregation: avg
```

### Snowflake Schema
Dimensional model where dimensions have sub-dimensions (normalized).

### Spark
Apache Spark, optional backend for distributed processing.

### Star Schema
Dimensional model with a central fact table surrounded by dimension tables.

### Storage Router
Component that resolves logical table names to physical storage paths.

---

## T

### Tier
Level in the model dependency graph.

- **Tier 0**: Foundation (core)
- **Tier 1**: Independent (company, macro)
- **Tier 2**: Dependent (stocks, options)
- **Tier 3**: Derived (forecast)

---

## U

### Unique Key
Columns that define uniqueness for deduplication.

```yaml
unique_key: [ticker]
```

### UniversalSession
Unified query interface for accessing all models.

```python
session = UniversalSession(backend="duckdb")
df = session.query("SELECT * FROM stocks.dim_stock")
```

---

## W

### Weighted Measure
Aggregation weighted by another column.

```yaml
weighted_measures:
  vwap:
    value_column: close
    weight_column: volume
    aggregation: weighted_avg
```

---

## Y

### YAML Configuration
Declarative model definitions in YAML format.

```yaml
model: stocks
version: 2.0
depends_on: [core, company]
```

---

## Related Documentation

- [Architecture](architecture.md) - System design
- [Core Framework](../01-core-framework/README.md) - BaseModel, sessions
- [Graph Architecture](../02-graph-architecture/README.md) - Graph concepts
