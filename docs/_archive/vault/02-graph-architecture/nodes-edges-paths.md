# Nodes, Edges, and Paths

**Detailed reference for graph components**

---

## Nodes

### Purpose

Nodes represent tables in your dimensional model. Each node corresponds to either a dimension or fact table in the Silver layer.

### Node Types

**Dimensions** (`dim_*`)
- Reference data
- Slowly changing
- Descriptive attributes
- Example: `dim_equity`, `dim_company`, `dim_calendar`

**Facts** (`fact_*`)
- Transactional data
- Rapidly growing
- Measurable events
- Example: `fact_equity_prices`, `fact_news`, `fact_forecasts`

### Node Configuration Schema

```yaml
nodes:
  - id: string                    # Required: Unique identifier
    from: string                  # Required: Source (bronze.table or node_id)
    select:                       # Optional: Column selection/aliasing
      output_name: source_column
    derive:                       # Optional: Computed columns
      output_name: expression
    unique_key: [column, ...]     # Optional: Deduplication constraint
```

### Node Loading

**From Bronze Layer**

```yaml
- id: dim_equity
  from: bronze.ref_ticker         # Loads from storage/bronze/ref_ticker/
  select:
    ticker: ticker
    name: name
```

**From Another Node**

```yaml
- id: fact_equity_prices
  from: bronze.prices_daily

- id: fact_prices_normalized
  from: fact_equity_prices         # Derives from existing node
  select:
    ticker: ticker
    date: trade_date
```

**Cannot Load Cross-Model Directly**

```yaml
# WRONG - Cannot load cross-model in nodes
- id: dim_calendar
  from: core.dim_calendar          # ❌ Not supported

# CORRECT - Use edges/paths for cross-model access
edges:
  - from: fact_equity_prices
    to: core.dim_calendar          # ✅ Correct way
```

### Select Transformations

Column selection and renaming.

**Syntax:**
```yaml
select:
  output_name: source_column
```

**Examples:**

```yaml
# Keep same name
select:
  ticker: ticker
  name: name

# Rename columns
select:
  equity_ticker: ticker
  company_name: name
  exchange_code: primary_exchange

# Select subset of columns
select:
  ticker: ticker
  close_price: close
  # open, high, low, volume omitted
```

**Backend Implementation:**
- **Spark**: Uses `select(F.col(source).alias(output))`
- **DuckDB**: Uses `project("source AS output")`

### Derive Transformations

Create computed columns using SQL expressions.

**Syntax:**
```yaml
derive:
  output_name: expression
```

**Supported Expressions:**

**Column References**
```yaml
derive:
  ticker_copy: ticker
```

**Hash Functions**
```yaml
derive:
  equity_key: sha1(ticker)
  company_key: md5(name)
```

**Arithmetic**
```yaml
derive:
  price_range: high - low
  returns: (close - open) / open * 100
  volume_millions: volume / 1000000
```

**String Operations**
```yaml
derive:
  upper_ticker: UPPER(ticker)
  name_length: LENGTH(name)
  ticker_prefix: SUBSTRING(ticker, 1, 2)
```

**Conditional Logic**
```yaml
derive:
  price_category: CASE WHEN close > 100 THEN 'high' ELSE 'low' END
  is_gain: CASE WHEN close > open THEN 1 ELSE 0 END
```

**Window Functions**
```yaml
derive:
  price_rank: ROW_NUMBER() OVER (ORDER BY close DESC)
  running_total: SUM(volume) OVER (ORDER BY trade_date)
  moving_avg: AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
```

**Date Functions**
```yaml
derive:
  year: YEAR(trade_date)
  month: MONTH(trade_date)
  quarter: QUARTER(trade_date)
  day_of_week: DAYOFWEEK(trade_date)
```

**Backend Implementation:**
- **Spark**: Uses `withColumn(name, F.expr(expression))`
- **DuckDB**: Uses SQL SELECT with temp table registration

**Error Handling:**

If derive expression fails:
- Warning logged
- Column skipped
- Build continues with remaining columns

Common failure causes:
- Unsupported function
- Nested window functions
- Invalid SQL syntax

### Unique Key Constraint

Enforce deduplication on node output.

**Syntax:**
```yaml
unique_key: [column1, column2, ...]
```

**Examples:**

**Single Column**
```yaml
- id: dim_equity
  from: bronze.ref_ticker
  unique_key: [ticker]              # Keep last occurrence per ticker
```

**Composite Key**
```yaml
- id: fact_equity_prices
  from: bronze.prices_daily
  unique_key: [ticker, trade_date]  # Keep last per ticker-date
```

**Backend Implementation:**
- **Spark**: Uses `dropDuplicates(columns)` (keeps last)
- **DuckDB**: Converts to pandas, uses `drop_duplicates(subset=columns, keep='last')`

**Use Cases:**
- Remove duplicate API responses
- Handle late-arriving data
- Enforce dimensional uniqueness

### Node Build Order

Nodes build in YAML definition order. Dependent nodes must come after their dependencies.

**Correct Order:**

```yaml
nodes:
  # Independent nodes first
  - id: dim_equity
    from: bronze.ref_ticker

  - id: fact_equity_prices
    from: bronze.prices_daily

  # Dependent nodes after
  - id: fact_prices_normalized
    from: fact_equity_prices
```

**Incorrect Order:**

```yaml
nodes:
  # WRONG: Dependency not built yet
  - id: fact_prices_normalized
    from: fact_equity_prices       # ❌ Not defined yet

  - id: fact_equity_prices
    from: bronze.prices_daily
```

**Error:** `Node 'fact_equity_prices' not found`

---

## Edges

### Purpose

Edges define relationships (foreign keys) between nodes. They enable:
- Relationship validation
- Automatic join path discovery
- Query planning
- Graph traversal

### Edge Configuration Schema

```yaml
edges:
  - from: string                  # Required: Source node
    to: string                    # Required: Target node
    on: [join_spec, ...]          # Optional: Join conditions
```

### Edge Types

**Local Edges** - Between nodes in same model
```yaml
edges:
  - from: fact_equity_prices
    to: dim_equity
    on: [ticker = ticker]
```

**Cross-Model Edges** - Between nodes in different models
```yaml
edges:
  - from: fact_equity_prices
    to: core.dim_calendar         # References core model
    on: [trade_date = date]

  - from: dim_equity
    to: corporate.dim_company     # References corporate model
    on: [ticker = ticker]
```

### Join Specifications

**Explicit Join Keys**

```yaml
# Single key
on: [ticker = ticker]

# Composite key
on: [ticker = ticker, exchange = exchange]

# Different column names
on: [trade_date = date]
on: [equity_id = id, exchange_code = code]
```

**Inferred Join Keys**

```yaml
# Auto-infer from common columns
on: []

# BaseModel finds columns with same name in both tables
# Uses them as join keys
```

**Parse Format:**

Input: `["ticker = ticker", "date = trade_date"]`

Output: `[("ticker", "ticker"), ("date", "trade_date")]`

### Edge Validation

BaseModel validates edges during build (Spark backend only).

**Validation Steps:**

1. Resolve both nodes (local or cross-model)
2. Parse join keys from `on` specification
3. Execute dry-run join with `limit(1)`
4. Raise error if join fails

**Example:**

```yaml
edges:
  - from: fact_equity_prices
    to: dim_equity
    on: [ticker = ticker]
```

**Validation Process:**

```python
# Pseudo-code
left = nodes["fact_equity_prices"].limit(1)
right = nodes["dim_equity"].limit(1)
pairs = [("ticker", "ticker")]

# Test join
result = left.join(right, on=[left.ticker == right.ticker], how="left")

# If successful: edge validated ✅
# If failed: raise error ❌
```

**Common Validation Errors:**

```
Edge validation failed: fact_prices -> dim_equity
Join pairs: [('ticker', 'ticker')]
Error: Column 'ticker' does not exist in dim_equity
```

**Causes:**
- Column name typo
- Column not in select transformation
- Source data missing column

**Note:** Validation skipped for DuckDB backend (not yet implemented)

### Cross-Model Edge Resolution

**Requirements:**
1. Target model in `depends_on` list
2. Session injected via `set_session()`
3. Target model built (lazy-loaded automatically)

**Resolution Process:**

```yaml
edges:
  - from: dim_equity
    to: corporate.dim_company
    on: [ticker = ticker]
```

```python
# Internal resolution
target = "corporate.dim_company"

# Parse model and table
model_name, table_name = target.split(".", 1)  # ("corporate", "dim_company")

# Get model instance
corporate_model = session.get_model_instance("corporate")

# Ensure built
corporate_model.ensure_built()

# Get table
dim_company = corporate_model.get_dimension_df("dim_company")

# Validate edge
left.join(dim_company, on=[left.ticker == dim_company.ticker])
```

### Edge Direction

Edges are directional: `from` → `to`

**Convention:**
- **from**: Fact table or child dimension
- **to**: Dimension or parent dimension

**Example:**

```yaml
# Fact → Dimension
edges:
  - from: fact_equity_prices      # Many rows per equity
    to: dim_equity                # One row per equity

# Dimension → Dimension (snowflake)
edges:
  - from: dim_equity              # Many equities per company
    to: corporate.dim_company     # One company entry
```

**Graph Traversal:**

Query planner uses edges to find join paths:

```
Query: "Get prices with company information"

Path: fact_equity_prices → dim_equity → corporate.dim_company

Edges used:
1. fact_equity_prices → dim_equity (on ticker)
2. dim_equity → corporate.dim_company (on ticker)
```

---

## Paths

### Purpose

Paths represent materialized views created by joining multiple nodes. They:
- Pre-compute common joins
- Optimize query performance
- Create denormalized analytics views
- Support complex multi-hop relationships

### Path Configuration Schema

```yaml
paths:
  - id: string                    # Required: Path identifier
    hops: string | [string, ...]  # Required: Join chain
```

### Path Syntax

**String Format** (recommended)

```yaml
paths:
  - id: equity_prices_with_company
    hops: fact_equity_prices -> dim_equity -> corporate.dim_company
```

**Array Format**

```yaml
paths:
  - id: equity_prices_with_company
    hops:
      - fact_equity_prices
      - dim_equity
      - corporate.dim_company
```

**Single-String Array** (parsed automatically)

```yaml
paths:
  - id: equity_prices_with_company
    hops: ["fact_equity_prices -> dim_equity -> corporate.dim_company"]
```

### Path Materialization Process

**Input:** `fact_equity_prices -> dim_equity -> corporate.dim_company`

**Steps:**

1. **Parse hops into chain**
   ```python
   chain = ["fact_equity_prices", "dim_equity", "corporate.dim_company"]
   ```

2. **Initialize with first node**
   ```python
   result = resolve_node("fact_equity_prices")
   ```

3. **Join each subsequent hop**
   ```python
   for i in range(1, len(chain)):
       current_node = chain[i]
       previous_node = chain[i-1]

       # Resolve node (supports cross-model)
       right = resolve_node(current_node)

       # Find edge
       edge = find_edge(previous_node, current_node)

       # Parse join keys
       pairs = parse_join_keys(edge["on"])

       # Join with deduplication
       result = join_with_dedupe(result, right, pairs, how="left")
   ```

4. **Return materialized DataFrame**

**Output:** DataFrame with columns from all three tables

### Path Examples

**Two-Hop Path**

```yaml
paths:
  - id: prices_with_equity_info
    hops: fact_equity_prices -> dim_equity
```

**Result Columns:**
- From `fact_equity_prices`: ticker, trade_date, open, close, volume
- From `dim_equity`: name, exchange, sector
- Deduplicated: Single `ticker` column

**Three-Hop Path**

```yaml
paths:
  - id: equity_prices_enriched
    hops: fact_equity_prices -> dim_equity -> corporate.dim_company
```

**Result Columns:**
- From `fact_equity_prices`: ticker, trade_date, open, close, volume
- From `dim_equity`: name, exchange, sector
- From `corporate.dim_company`: company_name, headquarters, industry
- Deduplicated: Single `ticker` column

**Cross-Model Path**

```yaml
paths:
  - id: equity_prices_with_calendar
    hops: fact_equity_prices -> dim_equity -> core.dim_calendar
```

**Multi-Model Path**

```yaml
paths:
  - id: full_equity_context
    hops: fact_equity_prices -> dim_equity -> corporate.dim_company
```

### Path Naming Conventions

Use descriptive names that indicate what the path contains:

```yaml
# Good names
- id: equity_prices_with_company
- id: news_with_company_info
- id: forecasts_enriched

# Avoid generic names
- id: path1
- id: joined_data
```

### Column Deduplication

When joining, duplicate columns are removed from the right side.

**Example:**

**Before Join:**
- Left: `[ticker, trade_date, close]`
- Right: `[ticker, name, exchange]`

**After Join:**
- Result: `[ticker, trade_date, close, name, exchange]`
- Right `ticker` column removed (duplicate)

**Implementation:**

```python
def _join_with_dedupe(left, right, pairs, how="left"):
    # Get join key columns
    join_cols = [r for l, r in pairs]

    # Join
    result = left.join(right, on=[left[l] == right[r] for l, r in pairs], how=how)

    # Remove duplicate columns from right
    for col in join_cols:
        if col in result.columns and f"{col}_right" in result.columns:
            result = result.drop(f"{col}_right")

    return result
```

### Path Limitations

**DuckDB Backend:**
- Path materialization not yet implemented
- `_materialize_paths()` returns empty dict
- Use query-time joins instead

**Spark Backend:**
- Full path support
- Paths persisted to Silver layer
- Available for query via `get_fact_df(path_id)`

### Path Output

Materialized paths are included in the **facts** dictionary:

```python
dims, facts = model.build()

# Regular facts
facts["fact_equity_prices"]

# Materialized paths (included in facts)
facts["equity_prices_with_company"]
```

**Storage:**

Paths written to Silver layer like regular facts:

```
storage/silver/equity/facts/
├── fact_equity_prices/
└── equity_prices_with_company/    # Materialized path
```

---

## Integration Example

Complete model with nodes, edges, and paths:

```yaml
model: equity
version: 1
depends_on:
  - core
  - corporate

graph:
  # Nodes: Define tables and transformations
  nodes:
    - id: dim_equity
      from: bronze.ref_ticker
      select:
        ticker: ticker
        name: name
        exchange: primary_exchange
      derive:
        equity_key: sha1(ticker)
        upper_ticker: UPPER(ticker)
      unique_key: [ticker]

    - id: fact_equity_prices
      from: bronze.prices_daily
      select:
        ticker: ticker
        trade_date: trade_date
        open_price: open
        close_price: close
        volume: volume
      derive:
        price_range: high - low
        returns: (close - open) / open * 100
      unique_key: [ticker, trade_date]

  # Edges: Define relationships
  edges:
    - from: fact_equity_prices
      to: dim_equity
      on: [ticker = ticker]

    - from: fact_equity_prices
      to: core.dim_calendar
      on: [trade_date = date]

    - from: dim_equity
      to: corporate.dim_company
      on: [ticker = ticker]

  # Paths: Materialized views
  paths:
    - id: equity_prices_with_company
      hops: fact_equity_prices -> dim_equity -> corporate.dim_company

    - id: equity_prices_with_calendar
      hops: fact_equity_prices -> core.dim_calendar
```

**Result:**

**Dimensions:**
- `dim_equity`: Equity reference data with computed columns

**Facts:**
- `fact_equity_prices`: Price data with computed metrics
- `equity_prices_with_company`: Prices joined with company info (path)
- `equity_prices_with_calendar`: Prices joined with calendar (path)

**Validated Relationships:**
- ✅ fact_equity_prices → dim_equity
- ✅ fact_equity_prices → core.dim_calendar
- ✅ dim_equity → corporate.dim_company

---

## Troubleshooting

### Node Errors

**"Node not found"**
- Check node ID spelling
- Ensure node defined before use
- Verify YAML syntax

**"Column does not exist"**
- Check Bronze table schema
- Verify select/derive column names
- Check for typos

**"Failed to apply derive expression"**
- Check SQL syntax
- Verify column references
- Review error logs for specific failure

### Edge Errors

**"Edge validation failed"**
- Verify both nodes exist
- Check join column names
- Ensure columns exist in select transformation

**"Cross-model reference failed"**
- Add model to `depends_on`
- Ensure session injected
- Build dependency models first

### Path Errors

**"Path materialization failed"**
- Verify all edges exist
- Check hop chain syntax
- Ensure intermediate nodes built

**"DuckDB paths not supported"**
- Expected: DuckDB skips path materialization
- Use query-time joins via UniversalSession

---

## Related Documentation

- [Graph Architecture Overview](graph-overview.md)
- [BaseModel Reference](../01-core-components/base-model.md)
- [YAML Configuration](../03-model-framework/yaml-configuration.md)
- [Cross-Model References](cross-model-references.md)
