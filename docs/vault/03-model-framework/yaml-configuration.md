# YAML Configuration Reference

**Model definition format and schema**

---

## Overview

Models in de_Funk are defined **declaratively** in YAML. The YAML config specifies schema, graph structure, and measures - BaseModel translates this into executable code.

**Location**: `configs/models/{model_name}.yaml`

---

## Complete Structure

```yaml
model: model_name
version: 1
depends_on: [dependent_model1, dependent_model2]

storage:
  root: storage/silver/model_name
  format: parquet

schema:
  dimensions:
    dim_table_name:
      path: dims/dim_table_name
      primary_key: [key_col]
      columns:
        column_name: data_type

  facts:
    fact_table_name:
      path: facts/fact_table_name
      partition_by: [partition_col]
      columns:
        column_name: data_type

graph:
  nodes:
    - id: dim_table_name
      type: dimension
    - id: fact_table_name
      type: fact

  edges:
    - from: fact_table
      to: dim_table
      on: ["fact_key=dim_key"]
      type: many_to_one

    - from: local_table
      to: other_model.remote_table
      on: ["local_col=remote_col"]
      type: left
      description: "Cross-model edge"

  paths:
    - id: fact_with_dims
      hops: fact_table -> dim1 -> dim2
      description: "Materialized joined view"

measures:
  measure_name:
    type: simple | computed | weighted
    source: table.column
    aggregation: avg | sum | min | max
    description: "Measure description"
```

---

## Section Reference

### model

**Required**: Unique model identifier

```yaml
model: equity
```

---

### version

**Required**: Schema version for migrations

```yaml
version: 1
```

---

### depends_on

**Optional**: List of models this model depends on

```yaml
depends_on: [core, corporate]
```

**Rules**:
- Foundation models (core) have no dependencies
- Cannot create circular dependencies
- Models must be built in dependency order

---

### storage

**Required**: Storage configuration

```yaml
storage:
  root: storage/silver/equity  # Silver layer path
  format: parquet              # Storage format
```

---

### schema

**Required**: Table definitions

#### dimensions

```yaml
dimensions:
  dim_equity:
    path: dims/dim_equity                # Relative to storage.root
    primary_key: [ticker]                # Primary key column(s)
    columns:
      ticker: string
      company_id: string
      company_name: string
      exchange_id: string
```

#### facts

```yaml
facts:
  fact_equity_prices:
    path: facts/fact_equity_prices
    partition_by: [trade_date]           # Partition columns
    columns:
      ticker: string
      trade_date: date
      open: double
      high: double
      low: double
      close: double
      volume: long
```

**Data Types**: `string`, `integer`, `long`, `double`, `float`, `date`, `timestamp`, `boolean`

---

### graph

**Required**: Graph structure

#### nodes

```yaml
nodes:
  - id: dim_equity
    type: dimension
  - id: fact_equity_prices
    type: fact
```

**Types**: `dimension`, `fact`

---

#### edges

**Within-Model Edge**:
```yaml
edges:
  - from: fact_equity_prices
    to: dim_equity
    on: ["ticker=ticker"]
    type: many_to_one
```

**Cross-Model Edge**:
```yaml
edges:
  - from: dim_equity
    to: corporate.dim_corporate
    on: ["company_id=company_id"]
    type: many_to_one
    description: "Equity belongs to corporate entity"
```

**Join Types**:
- `many_to_one` - Fact to dimension (most common)
- `one_to_many` - Dimension to fact
- `left` - Left outer join
- `inner` - Inner join

---

#### paths

**Materialized Views** (pre-computed joins):

```yaml
paths:
  - id: equity_prices_with_company
    hops: fact_equity_prices -> dim_equity -> corporate.dim_corporate
    description: "Prices with company fundamentals"
```

**Benefits**:
- Faster queries (joins pre-computed)
- Query planner uses paths when available

---

### measures

**Simple Measure**:
```yaml
measures:
  avg_close_price:
    type: simple
    source: fact_equity_prices.close
    aggregation: avg
    data_type: double
    description: "Average closing price"
```

**Computed Measure**:
```yaml
measures:
  daily_dollar_volume:
    type: computed
    source: fact_equity_prices.close
    expression: "close * volume"
    aggregation: sum
    description: "Total dollar volume"
```

**Weighted Measure**:
```yaml
measures:
  volume_weighted_price:
    type: weighted
    source: fact_equity_prices.close
    weighting_method: volume
    group_by: [trade_date]
    description: "Volume-weighted average price"
```

**Cross-Model Measure**:
```yaml
measures:
  holdings_weighted_return:
    type: weighted
    source: equity.fact_equity_prices.close  # Cross-model reference
    weighting_method: holdings_weight
```

---

## Validation Rules

1. **Unique IDs**: All node IDs must be unique within model
2. **Edge Validity**: `from` and `to` must reference valid nodes
3. **Column Existence**: Edge join columns must exist in table schemas
4. **Dependency Validity**: All `depends_on` models must exist
5. **No Circular Deps**: Dependency graph must be acyclic

---

## Examples

See actual model configs in `/configs/models/`:
- `core.yaml` - Foundation model (calendar)
- `equity.yaml` - Stock market data
- `corporate.yaml` - Company entities
- `macro.yaml` - Economic indicators

---

## Related Documentation

- [BaseModel](../01-core-components/base-model.md) - How YAML is parsed and executed
- [Model Lifecycle](model-lifecycle.md) - Build process
- [Measure Framework](measure-framework.md) - Measure types
- [Dependency Resolution](../02-graph-architecture/dependency-resolution.md) - Build order
