# Domain Model Template Specification v4.0

**Status**: Reference Documentation
**Updated**: 2026-01-27

---

## Overview

This document defines the template structure for domain models in de_Funk. There are exactly **two model types** and **one inheritance mechanism**.

**Key Design**: Schema and transformation info are unified in `tables:`. The `graph:` section is a **relationship map** showing nodes, edges, and paths for easy reference - no schema duplication.

---

## Type Values

| Type | Purpose | Gets Built? |
|------|---------|-------------|
| `type: domain-base` | Reusable template | NO |
| `type: domain-model` | Actual model | YES |

---

## Unified Table Structure

All table information is in ONE place - the `tables:` section. No duplication.

```yaml
tables:
  dim_example:
    type: dimension
    from: bronze.{provider}.{table}      # Data source (was in graph.nodes)
    filters:                              # Row filters (was in graph.nodes)
      - "column = 'value'"
    primary_key: [id]
    unique_key: [name]

    schema:
      # Format: [name, type, nullable, description, {options}]
      # Column options include source mapping and derivation
      - [id, integer, false, "PK", {derive: "ABS(HASH(name))"}]
      - [name, string, false, "Name", {from: source_field}]
      - [status, string, true, "Status", {from: status_col, default: "active"}]
      - [created_at, timestamp, false, "Created", {derive: "CURRENT_TIMESTAMP()"}]

    measures:
      - [count, count, id, "Count", {format: "#,##0"}]

graph:
  # Graph = relationship MAP (no schema, just keys for easy reference)
  nodes:
    dim_example: {pk: id}
    fact_example: {pk: id}

  edges:
    fact_to_dim: {from: fact_example, to: dim_example, fk: dim_id}
    fact_to_calendar: {from: fact_example, to: temporal.dim_calendar, fk: date_id}

  paths:
    calendar_to_dim:
      description: "Navigate from calendar through fact to dimension"
      via: [temporal.dim_calendar, fact_example, dim_example]
```

---

## Schema Column Options

```yaml
schema:
  # Format: [name, type, nullable, description, {options}]
  - [column_name, type, true/false, "Description", {option: value}]
```

### Source Mapping Options

| Option | Purpose | Example |
|--------|---------|---------|
| `{from: col}` | Map from source column | `{from: source_name}` |
| `{derive: "expr"}` | Compute from expression | `{derive: "ABS(HASH(name))"}` |

**Rules**:
- Column must have EITHER `from:` OR `derive:` (not both, not neither)
- Exception: Columns inherited from base template
- Exception: `{computed: true}` for post-build calculations

### Constraint Options

| Option | Purpose | Example |
|--------|---------|---------|
| `{fk: table.column}` | Foreign key reference | `{fk: temporal.dim_calendar.date_id}` |
| `{unique: true}` | Unique constraint | `{unique: true}` |
| `{default: value}` | Default value | `{default: "USD"}` |
| `{enum: [a, b, c]}` | Allowed values | `{enum: [stocks, etf, option]}` |
| `{computed: true}` | Computed post-build | `{computed: true}` |

### Types

| Type | Description |
|------|-------------|
| `integer` | 32-bit integer |
| `long` | 64-bit integer |
| `double` | 64-bit float |
| `string` | Text |
| `boolean` | true/false |
| `date` | Date only |
| `timestamp` | Date + time |

---

## Template Structure (`type: domain-base`)

Base templates live in `domains/_base/` and define reusable schemas.

```yaml
---
type: domain-base
base_name: {template_name}
version: 3.0
description: "Template description"
tags: [base, template]

# Tables use _ prefix to indicate template
tables:
  _dim_example:
    type: dimension
    # NO 'from:' in templates - child provides data source
    primary_key: [id]
    schema:
      # Template columns - child maps to these
      - [id, integer, false, "PK"]
      - [name, string, false, "Name"]

  _fact_example:
    type: fact
    primary_key: [id]
    schema:
      - [id, integer, false, "PK"]
      - [dim_id, integer, false, "FK", {fk: _dim_example.id}]

# NO graph section in templates - child defines relationships
status: active
---

## Template Documentation

Markdown documentation here.
```

### Key Points

- `type: domain-base` - never gets built
- `base_name:` - identifier for extends reference
- Table names start with `_` - indicates template
- NO `from:` in templates - child provides data source
- NO `graph:` section - templates define schema only, child defines relationships

---

## Model Structure (`type: domain-model`)

Built models live in `domains/{category}/` and produce actual tables.

```yaml
---
type: domain-model
model: {model_name}
version: 3.0
description: "Model description"
tags: [model, category]

# Optional: inherit from base template
extends: _base.{category}.{base_name}

# Dependencies (build order)
depends_on: [temporal, other_model]

# Storage configuration
storage:
  format: delta
  bronze:
    provider: {provider_name}
    tables:
      {table_alias}: {provider}/{endpoint}
  silver:
    root: storage/silver/{model}

# Build configuration
build:
  partitions: [partition_col]
  sort_by: [sort_col]
  optimize: true

# Tables - unified schema + transformation
tables:
  dim_example:
    type: dimension
    from: bronze.{provider}.{table}
    filters:
      - "status = 'active'"
    primary_key: [id]
    unique_key: [name]

    schema:
      - [id, integer, false, "PK", {derive: "ABS(HASH(name))"}]
      - [name, string, false, "Name", {from: source_name, unique: true}]
      - [category, string, true, "Category", {from: cat_code}]

    measures:
      - [count, count, id, "Count", {format: "#,##0"}]

  fact_example:
    type: fact
    from: bronze.{provider}.{table}
    filters:
      - "value IS NOT NULL"
    primary_key: [id]
    partition_by: [date_id]

    schema:
      - [id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(dim_id, '_', date_id)))"}]
      - [dim_id, integer, false, "FK to dim", {derive: "ABS(HASH(name))", fk: dim_example.id}]
      - [date_id, integer, false, "FK to calendar", {derive: "CAST(REGEXP_REPLACE(CAST(date AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [value, double, false, "Value", {from: amount}]

    measures:
      - [total, sum, value, "Total", {format: "$#,##0.00"}]

# Graph - relationship map (no schema duplication)
graph:
  nodes:
    dim_example: {pk: id}
    fact_example: {pk: id}

  edges:
    fact_to_dim: {from: fact_example, to: dim_example, fk: dim_id}
    fact_to_calendar: {from: fact_example, to: temporal.dim_calendar, fk: date_id}

  paths:
    calendar_to_dim:
      description: "Navigate from calendar through fact to dimension"
      via: [temporal.dim_calendar, fact_example, dim_example]

metadata:
  domain: {domain}
  owner: {team}
status: active
---

## Model Documentation

Markdown documentation here.
```

---

## Inheritance (`extends:`)

Models inherit from base templates using `extends:`.

### Pattern

```yaml
# In domains/{category}/{model}.md
type: domain-model
model: my_model
extends: _base.{category}.{base_name}

tables:
  dim_mine:
    from: bronze.{provider}.{table}  # Child provides data source
    # Inherits schema from _base.{category}.{base_name}._dim_example
    # Add model-specific columns with source mapping:
    schema:
      - [extra_col, string, true, "Additional column", {from: extra_source}]
```

### Example: temporal extends _base.temporal.calendar

**Base** (`_base/temporal/calendar.md`):
```yaml
type: domain-base
base_name: calendar

tables:
  dim_calendar:
    # No 'from:' - child provides data source (or self-generated)
    schema:
      - [date_id, integer, false, "PK"]
      - [date, date, false, "Date"]
      - [year, integer, false, "Year"]
      # ... standard calendar columns
```

**Model** (`temporal/temporal.md`):
```yaml
type: domain-model
model: temporal
extends: _base.temporal.calendar

depends_on: []

calendar_config:
  start_date: "2000-01-01"
  end_date: "2050-12-31"

tables:
  dim_calendar:
    from: self  # Generated programmatically, not from bronze
    # Inherits all base columns, adds:
    schema:
      - [is_trading_day, boolean, true, "NYSE trading day", {default: true}]
      - [is_holiday, boolean, true, "US federal holiday", {default: false}]
```

---

## Table-Level Options

```yaml
tables:
  table_name:
    type: dimension | fact              # Required: table type
    from: bronze.{provider}.{table}     # Required: data source
    filters:                            # Optional: row filters (WHERE)
      - "column = 'value'"
      - "other_column IS NOT NULL"
    primary_key: [col1, col2]           # Required: primary key columns
    unique_key: [natural_key]           # Optional: natural key
    partition_by: [date_id]             # Optional: partition columns (facts)
    description: "Table description"    # Optional: documentation
```

### Data Sources (`from:`)

| Source Type | Example | Use Case |
|-------------|---------|----------|
| Bronze table | `bronze.alpha_vantage.listing_status` | Raw ingested data |
| Another model | `securities.fact_security_prices` | Reference master |
| Self-generated | `self` | Programmatic generation |
| Computed | `computed` | Post-build calculation |

### Referencing Other Models

```yaml
tables:
  fact_filtered:
    from: {other_model}.{table_name}    # Reference another model's table
    filters:
      - "type = 'specific_value'"       # Filter the source
    schema:
      - [id, integer, false, "PK", {from: id}]
      - [value, double, false, "Value", {from: value}]
```

---

## Measures Format

Measures are defined on tables in the `tables:` section.

```yaml
tables:
  fact_example:
    # ... schema ...
    measures:
      # Format: [name, aggregation, source, description, {options}]
      - [measure_name, aggregation, source_column, "Description", {format: "..."}]
```

### Aggregations

| Aggregation | SQL |
|-------------|-----|
| `count` | COUNT(column) |
| `count_distinct` | COUNT(DISTINCT column) |
| `sum` | SUM(column) |
| `avg` | AVG(column) |
| `min` | MIN(column) |
| `max` | MAX(column) |
| `expression` | Custom SQL expression |

### Expression Measures

```yaml
measures:
  - [custom_calc, expression, "SUM(a) / SUM(b) * 100", "Percentage", {format: "#,##0.0%"}]
```

---

## Graph Section (Relationship Map)

The `graph:` section is a **relationship map** for easy reference - no schema duplication. It shows:
- **Nodes**: Tables with their primary keys
- **Edges**: FK relationships (can be auto-validated against schema)
- **Paths**: Named multi-hop traversals

```yaml
graph:
  # Nodes - index of tables with PKs (no schema)
  nodes:
    dim_example: {pk: id}
    fact_example: {pk: id}

  # Edges - FK relationships (compact format)
  edges:
    edge_name: {from: source_table, to: target_table, fk: fk_column}
    edge_name: {from: source_table, to: target_table, fk: fk_column, optional: true}

  # Paths - named multi-hop traversals
  paths:
    path_name:
      description: "Human-readable description"
      via: [table_a, table_b, table_c]
```

### Graph Structure

| Section | Purpose | Contains |
|---------|---------|----------|
| `nodes:` | Index of tables | Table name + PK only |
| `edges:` | Index of relationships | from/to/fk (compact) |
| `paths:` | Multi-hop traversals | Named paths with steps |

### Edge Format (Compact)

```yaml
edges:
  # Same-model edges
  fact_to_dim: {from: fact_prices, to: dim_security, fk: security_id}

  # Cross-model edges
  to_calendar: {from: fact_prices, to: temporal.dim_calendar, fk: date_id}
  to_master: {from: dim_stock, to: securities.dim_security, fk: security_id}

  # Optional (outer join)
  to_company: {from: dim_stock, to: company.dim_company, fk: company_id, optional: true}
```

### Paths Format

```yaml
paths:
  prices_to_sector:
    description: "Navigate from prices to sector via stock and company"
    via: [securities.fact_security_prices, dim_stock, company.dim_company]
```

### Graph vs Schema: Relationship

The `graph:` section is a **map** of relationships - not the source of truth. The source of truth is the `{fk: table.column}` option in schema:

```yaml
# Schema defines the FK (source of truth)
schema:
  - [security_id, integer, false, "FK", {fk: securities.dim_security.security_id}]

# Graph maps it for easy reference (can be auto-validated)
edges:
  stock_to_security: {from: dim_stock, to: securities.dim_security, fk: security_id}
```

**Benefits of this approach:**
1. **Schema is authoritative** - FKs in schema drive the build
2. **Graph is documentation** - Easy to see all relationships at a glance
3. **Auto-validation** - Builder can verify graph matches schema FKs
4. **Query guidance** - Paths help users construct complex joins

---

## Directory Structure

```
domains/
├── _base/                    # Templates (type: domain-base)
│   ├── temporal/
│   │   └── calendar.md
│   ├── finance/
│   │   └── securities.md
│   ├── geospatial/
│   │   └── geospatial.md
│   └── public_safety/
│       └── crime.md
│
├── temporal/                 # Foundation (type: domain-model)
│   └── temporal.md          # extends: _base.temporal.calendar
│
├── securities/               # Securities family
│   ├── securities.md        # Master
│   ├── stocks.md            # Uses from: securities.fact_security_prices
│   └── forecast/
│       └── forecast.md
│
├── corporate/
│   └── company.md
│
├── geospatial/
│   └── geospatial.md
│
└── municipal/
    └── chicago/
        ├── geospatial.md    # extends: _base.geospatial.geospatial
        ├── public_safety.md # extends: _base.public_safety.crime
        ├── operations.md
        ├── regulatory.md
        ├── housing.md
        ├── finance.md
        └── transportation.md
```

---

## Master-Child Relationship Guidance

When a child model relates to a master model, decide whether the child **copies** or **references** the master's tables.

### Decision: Copy vs Reference

| Child needs... | Action | Example |
|----------------|--------|---------|
| Filtered subset with NO additions | Reference master directly | Query `securities.fact_security_prices WHERE asset_type='stocks'` |
| Filtered subset WITH additions | Create dimension only, reference master fact | `dim_stock` + reference `securities.fact_security_prices` |
| Completely different schema | Build own tables from bronze | Separate bronze source |

### Recommended Pattern: Reference, Don't Copy

**Do NOT duplicate master fact tables in children.**

```
WRONG (duplicates data):
─────────────────────────
securities
├── dim_security
└── fact_security_prices  ←── ALL prices

stocks
├── dim_stock
└── fact_stock_prices     ←── COPY of prices (duplication!)
```

```
RIGHT (reference master):
─────────────────────────
securities
├── dim_security
└── fact_security_prices  ←── ALL prices (single source)

stocks
├── dim_stock             ←── Filtered dimension (stock-specific attrs)
├── fact_stock_technicals ←── Extension (computed from master prices)
├── fact_dividends        ←── Extension (stock-specific data)
└── fact_splits           ←── Extension (stock-specific data)

    (NO fact_stock_prices - query securities directly)
```

### Child Model Structure (Unified)

```yaml
type: domain-model
model: stocks
depends_on: [temporal, securities, company]

tables:
  # Dimension: filtered from bronze, links to master
  dim_stock:
    type: dimension
    from: bronze.alpha_vantage.listing_status
    filters:
      - "asset_type = 'stocks'"
    primary_key: [stock_id]
    unique_key: [ticker]

    schema:
      - [stock_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "FK to master", {derive: "ABS(HASH(ticker))", fk: securities.dim_security.security_id}]
      - [company_id, integer, true, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', ticker)))", fk: company.dim_company.company_id}]
      - [ticker, string, false, "Trading symbol", {from: ticker, unique: true}]
      - [security_name, string, true, "Name", {from: name}]
      - [exchange_code, string, true, "Exchange", {from: exchange}]
      - [stock_type, string, true, "Type", {derive: "'common'"}]

  # Extension: computed from master prices (post-build)
  fact_stock_technicals:
    type: fact
    from: computed
    primary_key: [technical_id]
    partition_by: [date_id]

    schema:
      - [technical_id, integer, false, "PK", {derive: "ABS(HASH(...))"}]
      - [security_id, integer, false, "FK", {from: security_id, fk: dim_stock.security_id}]
      - [date_id, integer, false, "FK", {from: date_id, fk: temporal.dim_calendar.date_id}]
      - [sma_20, double, true, "20-day SMA", {computed: true}]
      - [rsi_14, double, true, "14-day RSI", {computed: true}]

  # Extension: stock-specific bronze data
  fact_dividends:
    type: fact
    from: bronze.alpha_vantage.dividends
    primary_key: [dividend_id]

    schema:
      - [dividend_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(ticker, '_', ex_date)))"}]
      - [security_id, integer, false, "FK", {derive: "ABS(HASH(ticker))", fk: dim_stock.security_id}]
      - [ex_dividend_date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST(ex_date AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [dividend_amount, double, false, "Amount", {from: amount}]

  # NO fact_stock_prices - query securities.fact_security_prices directly

graph:
  nodes:
    dim_stock: {pk: stock_id}
    fact_stock_technicals: {pk: technical_id}
    fact_dividends: {pk: dividend_id}

  edges:
    stock_to_security: {from: dim_stock, to: securities.dim_security, fk: security_id}
    stock_to_company: {from: dim_stock, to: company.dim_company, fk: company_id, optional: true}
    technicals_to_stock: {from: fact_stock_technicals, to: dim_stock, fk: security_id}
    technicals_to_calendar: {from: fact_stock_technicals, to: temporal.dim_calendar, fk: date_id}
    dividends_to_stock: {from: fact_dividends, to: dim_stock, fk: security_id}
    dividends_to_calendar: {from: fact_dividends, to: temporal.dim_calendar, fk: date_id}

  paths:
    prices_to_sector:
      description: "Master prices to company sector"
      via: [securities.fact_security_prices, dim_stock, company.dim_company]
```

### Query Pattern

Join child dimension to master fact:

```sql
-- Stock prices with technicals
SELECT
    s.ticker,
    c.date,
    p.close,
    p.volume,
    t.rsi_14,
    t.sma_50
FROM securities.fact_security_prices p        -- Master prices
JOIN stocks.dim_stock s ON p.security_id = s.security_id  -- Child dimension
JOIN stocks.fact_stock_technicals t ON p.security_id = t.security_id
                                    AND p.date_id = t.date_id  -- Child extension
JOIN temporal.dim_calendar c ON p.date_id = c.date_id
WHERE p.asset_type = 'stocks'
```

### Summary

| Table Type | Where It Lives | Why |
|------------|----------------|-----|
| Unified fact (prices) | Master only | Single source of truth |
| Filtered dimension | Child | Child-specific attributes |
| Extension facts | Child | Child-specific data |
| Computed facts | Child | Derived from master |

---

## Common Patterns

### Pattern 1: Foundation Model

No dependencies, often generated (not from bronze).

```yaml
type: domain-model
model: temporal
extends: _base.temporal.calendar
depends_on: []  # No dependencies

tables:
  dim_calendar:
    from: self  # Generated programmatically
    primary_key: [date_id]
    # Inherits base schema, adds:
    schema:
      - [is_trading_day, boolean, true, "NYSE trading day", {default: true}]
      - [is_holiday, boolean, true, "US federal holiday", {default: false}]

graph:
  nodes:
    dim_calendar: {pk: date_id}

  edges: {}  # Other models link TO temporal

  paths: {}
```

### Pattern 2: Master Model

Holds unified data that children filter from.

```yaml
type: domain-model
model: securities
depends_on: [temporal]

tables:
  dim_security:
    from: bronze.alpha_vantage.listing_status
    primary_key: [security_id]
    schema:
      - [security_id, integer, false, "PK", {derive: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Symbol", {from: ticker, unique: true}]
      - [asset_type, string, false, "Type", {from: assetType}]
      # ALL securities (stocks, ETFs, options, futures)

  fact_security_prices:
    from: bronze.alpha_vantage.time_series_daily_adjusted
    primary_key: [price_id]
    partition_by: [date_id]
    schema:
      - [price_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(ticker, '_', date)))"}]
      - [security_id, integer, false, "FK", {derive: "ABS(HASH(ticker))", fk: dim_security.security_id}]
      - [date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST(date AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [close, double, false, "Close", {from: close}]
      - [volume, long, true, "Volume", {from: volume}]
      # ALL prices in one table

graph:
  nodes:
    dim_security: {pk: security_id}
    fact_security_prices: {pk: price_id}

  edges:
    prices_to_security: {from: fact_security_prices, to: dim_security, fk: security_id}
    prices_to_calendar: {from: fact_security_prices, to: temporal.dim_calendar, fk: date_id}

  paths: {}
```

### Pattern 3: Child Model (References Master)

Creates filtered dimension, references master fact (does NOT copy it).

```yaml
type: domain-model
model: stocks
depends_on: [temporal, securities, company]

tables:
  dim_stock:
    from: bronze.alpha_vantage.listing_status
    filters:
      - "asset_type = 'stocks'"  # Filter to stocks only
    primary_key: [stock_id]
    schema:
      - [stock_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "FK to master", {derive: "ABS(HASH(ticker))", fk: securities.dim_security.security_id}]
      - [ticker, string, false, "Symbol", {from: ticker}]

  fact_technicals:
    from: computed  # Post-build from master prices
    # ... technical indicators

  fact_dividends:
    from: bronze.alpha_vantage.dividends  # Stock-specific data
    # ...

  # NO fact_stock_prices - query securities.fact_security_prices directly

graph:
  nodes:
    dim_stock: {pk: stock_id}
    fact_technicals: {pk: technical_id}
    fact_dividends: {pk: dividend_id}

  edges:
    stock_to_master: {from: dim_stock, to: securities.dim_security, fk: security_id}
    stock_to_company: {from: dim_stock, to: company.dim_company, fk: company_id, optional: true}
    technicals_to_stock: {from: fact_technicals, to: dim_stock, fk: security_id}
    dividends_to_stock: {from: fact_dividends, to: dim_stock, fk: security_id}

  paths:
    prices_to_sector:
      description: "Master prices to company sector"
      via: [securities.fact_security_prices, dim_stock, company.dim_company]
```

### Pattern 4: Extended Model (Inherits from Template)

Inherits from base template, adds domain-specific columns.

```yaml
type: domain-model
model: chicago_public_safety
extends: _base.public_safety.crime

tables:
  fact_crimes:
    from: bronze.chicago.crimes
    # Inherits base crime schema, adds Chicago-specific:
    schema:
      - [ward, integer, true, "City ward", {from: ward}]
      - [community_area, integer, true, "Community area", {from: community_area}]
```

---

## Checklist: Adding a New Model

1. **Choose type**:
   - Need reusable template? → `type: domain-base` in `_base/`
   - Building actual tables? → `type: domain-model`

2. **Check for base template**:
   - Similar model exists in `_base/`? → Use `extends:`
   - No template? → Create from scratch or create base first

3. **Declare dependencies**:
   - Uses `date_id`? → Add `temporal` to `depends_on`
   - References other model? → Add to `depends_on`

4. **Define storage**:
   - List bronze tables needed
   - Set silver root path

5. **Define tables** (unified structure):
   - `from:` - data source
   - `filters:` - row filters
   - `primary_key:`, `unique_key:`
   - `schema:` with column options:
     - `{from: source_col}` - source mapping
     - `{derive: "expr"}` - computed columns
     - `{fk: table.col}` - foreign keys
   - `measures:` - aggregations

6. **Define graph** (relationship map):
   - `nodes:` - list tables with PKs
   - `edges:` - FK relationships (compact format)
   - `paths:` - named multi-hop traversals
   - Cross-model edges if needed

7. **Add documentation**:
   - Markdown section after `---`

---

## Quick Reference

| Keyword | Location | Purpose |
|---------|----------|---------|
| `type:` | root | `domain-model` or `domain-base` |
| `extends:` | root | Inherit from base template |
| `depends_on:` | root | Build order dependencies |
| `from:` | table | Data source |
| `filters:` | table | Row filters (WHERE clause) |
| `{from: col}` | schema option | Map from source column |
| `{derive: "expr"}` | schema option | Computed column expression |
| `{fk: table.col}` | schema option | Foreign key reference |
| `{unique: true}` | schema option | Unique constraint |
| `{default: val}` | schema option | Default value |
| `{computed: true}` | schema option | Post-build calculation |
| `nodes:` | graph | Table index with PKs |
| `edges:` | graph | FK relationship index |
| `paths:` | graph | Named multi-hop traversals |

---

## Appendix A: Two Mechanisms Explained

There are **two separate mechanisms** that can work together or independently:

### Mechanism 1: Schema Inheritance (`extends:`)

**Purpose**: Reuse column definitions across models.

```
_base/finance/securities.md          securities/securities.md
type: domain-base                    type: domain-model
                                     extends: _base.finance.securities
tables:                                       │
  _dim_security:        ─────────────────────►│
    # NO 'from:' - template only              │
    schema:                                   ▼
      - [security_id, ...]             tables:
      - [ticker, ...]                    dim_security:
      - [asset_type, ...]                  from: bronze.alpha_vantage.listing_status
                                             # Inherits columns, adds source mapping
  _fact_prices_base:    ─────────────────────►│
    schema:                                   │
      - [price_id, ...]                       ▼
      - [open, ...]                      fact_security_prices:
      - [close, ...]                       from: bronze.alpha_vantage.time_series_daily
                                             # Inherits columns, adds source mapping
```

**Key points**:
- `_base/` templates are NOT built (no tables created)
- Templates have NO `from:` - child provides data source
- `extends:` copies schema definitions into the child
- Child adds `from:` and `{from: col}` / `{derive: expr}` options

### Mechanism 2: Data Reference (`from:` + `depends_on:`)

**Purpose**: Reference another model's built tables.

```
securities/securities.md             stocks/stocks.md
type: domain-model                   type: domain-model
                                     depends_on: [securities]
tables:
  dim_security:         ◄────────────── edges:
    (12,499 rows)                         stock_to_security:
                                            to: securities.dim_security
  fact_security_prices: ◄────────────── Query directly:
    (ALL prices)                          FROM securities.fact_security_prices
                                          WHERE asset_type = 'stocks'
```

**Key points**:
- Both models ARE built (tables created)
- `depends_on:` ensures build order
- Child queries master's tables directly via edges
- Child does NOT copy master's data

### How They Differ

| Aspect | Schema Inheritance | Data Reference |
|--------|-------------------|----------------|
| Keyword | `extends:` | `from:` (table), `depends_on:` |
| Source | `_base/` template | Built model |
| What's shared | Column definitions | Actual data |
| Source built? | NO | YES |
| Creates copy? | NO (inherits schema) | NO (references in place) |

### How They Combine

A model can use BOTH mechanisms:

```yaml
# stocks/stocks.md
type: domain-model
model: stocks

# Mechanism 1: Schema inheritance (optional)
extends: _base.finance.securities

# Mechanism 2: Data reference
depends_on: [temporal, securities, company]

tables:
  dim_stock:
    from: bronze.alpha_vantage.listing_status
    filters:
      - "asset_type = 'stocks'"
    primary_key: [stock_id]
    schema:
      - [stock_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "FK to master", {derive: "ABS(HASH(ticker))", fk: securities.dim_security.security_id}]
      - [ticker, string, false, "Symbol", {from: ticker}]

graph:
  nodes:
    dim_stock: {pk: stock_id}

  edges:
    stock_to_security: {from: dim_stock, to: securities.dim_security, fk: security_id}

  paths: {}
```

---

## Appendix B: Current State vs Recommended

### Current State (Has Issues)

```
_base/finance/securities.md     ──── EXISTS but UNUSED
  type: domain-base
  _dim_security
  _fact_prices_base

securities/securities.md        ──── Standalone (no extends:)
  type: domain-model
  dim_security
  fact_security_prices

stocks/stocks.md                ──── DUPLICATES prices
  type: domain-model
  dim_stock
  fact_stock_prices             ◄─── PROBLEM: Copy of master
  fact_stock_technicals
  fact_dividends
  fact_splits
```

**Issues**:
1. `_base/finance/securities.md` exists but `securities.md` doesn't use it
2. `stocks.md` creates `fact_stock_prices` which duplicates `securities.fact_security_prices`

### Recommended State

```
_base/finance/securities.md     ──── Schema template
  type: domain-base
  _dim_security
  _fact_prices_base

securities/securities.md        ──── Master (uses template)
  type: domain-model
  extends: _base.finance.securities
  dim_security                  ◄─── Inherits + extends schema
  fact_security_prices          ◄─── ALL prices, single source

stocks/stocks.md                ──── Child (references master)
  type: domain-model
  depends_on: [securities]
  dim_stock                     ◄─── Filtered dimension
  fact_stock_technicals         ◄─── Extension (computed)
  fact_dividends                ◄─── Extension (bronze)
  fact_splits                   ◄─── Extension (bronze)
  (NO fact_stock_prices)        ◄─── Query master directly
```

### Changes Required

| File | Change |
|------|--------|
| `securities/securities.md` | Add `extends: _base.finance.securities` |
| `stocks/stocks.md` | Remove `fact_stock_prices` node and edges |

---

## Appendix C: Complete Example (Unified Structure)

### Layer 1: Base Template

```yaml
# domains/_base/finance/securities.md
---
type: domain-base
base_name: securities
description: "Base template for tradable securities"

tables:
  _dim_security:
    type: dimension
    # NO 'from:' - child provides data source
    primary_key: [security_id]
    schema:
      # Template columns - no source mapping needed
      - [security_id, integer, false, "PK"]
      - [ticker, string, false, "Trading symbol", {unique: true}]
      - [security_name, string, true, "Display name"]
      - [asset_type, string, false, "Type: stocks, etf, option, future"]
      - [exchange_code, string, true, "Exchange"]
      - [currency, string, true, "Currency", {default: "USD"}]
      - [is_active, boolean, true, "Currently trading", {default: true}]

  _fact_prices_base:
    type: fact
    # NO 'from:' - child provides data source
    primary_key: [price_id]
    partition_by: [date_id]
    schema:
      - [price_id, integer, false, "PK"]
      - [security_id, integer, false, "FK", {fk: _dim_security.security_id}]
      - [date_id, integer, false, "FK", {fk: temporal.dim_calendar.date_id}]
      - [open, double, true, "Open price"]
      - [high, double, true, "High price"]
      - [low, double, true, "Low price"]
      - [close, double, false, "Close price"]
      - [volume, long, true, "Volume"]
      - [adjusted_close, double, true, "Adjusted close"]

# NO graph section in templates
status: active
---
```

### Layer 2: Master Model

```yaml
# domains/securities/securities.md
---
type: domain-model
model: securities
version: 3.0
description: "Master securities - all instruments and prices"

extends: _base.finance.securities

depends_on: [temporal]

storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      listing_status: alpha_vantage/listing_status
      time_series_daily_adjusted: alpha_vantage/time_series_daily_adjusted
  silver:
    root: storage/silver/securities

tables:
  dim_security:
    from: bronze.alpha_vantage.listing_status
    primary_key: [security_id]
    unique_key: [ticker]

    # Inherits base columns, adds source mapping and extensions
    schema:
      # Inherited columns with source mapping
      - [security_id, integer, false, "PK", {derive: "ABS(HASH(ticker))"}]
      - [ticker, string, false, "Trading symbol", {from: ticker, unique: true}]
      - [security_name, string, true, "Display name", {from: name}]
      - [asset_type, string, false, "Type", {from: assetType}]
      - [exchange_code, string, true, "Exchange", {from: exchange}]
      - [currency, string, true, "Currency", {derive: "'USD'"}]
      - [is_active, boolean, true, "Currently trading", {derive: "delistingDate IS NULL"}]
      # Master-specific extensions
      - [ipo_date, date, true, "IPO date", {from: ipoDate}]
      - [delisting_date, date, true, "Delisting date", {from: delistingDate}]

    measures:
      - [security_count, count_distinct, security_id, "Number of securities", {format: "#,##0"}]

  fact_security_prices:
    from: bronze.alpha_vantage.time_series_daily_adjusted
    filters:
      - "timestamp IS NOT NULL"
      - "ticker IS NOT NULL"
    primary_key: [price_id]
    partition_by: [date_id]

    # Inherits base columns, adds source mapping and extensions
    schema:
      # Inherited columns with source mapping
      - [price_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(ticker, '_', CAST(timestamp AS STRING))))"}]
      - [security_id, integer, false, "FK", {derive: "ABS(HASH(ticker))", fk: dim_security.security_id}]
      - [date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST(timestamp AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [open, double, true, "Open price", {from: open}]
      - [high, double, true, "High price", {from: high}]
      - [low, double, true, "Low price", {from: low}]
      - [close, double, false, "Close price", {from: close}]
      - [volume, long, true, "Volume", {from: volume}]
      - [adjusted_close, double, true, "Adjusted close", {from: adjusted_close}]
      # Master-specific extensions (denormalized for convenience)
      - [asset_type, string, false, "For partition pruning", {derive: "'stocks'"}]
      - [trade_date, date, false, "Trade date", {from: timestamp}]
      - [ticker, string, false, "Ticker", {from: ticker}]

    measures:
      - [avg_close, avg, close, "Average closing price", {format: "$#,##0.00"}]
      - [total_volume, sum, volume, "Total volume", {format: "#,##0"}]

graph:
  nodes:
    dim_security: {pk: security_id}
    fact_security_prices: {pk: price_id}

  edges:
    prices_to_security: {from: fact_security_prices, to: dim_security, fk: security_id}
    prices_to_calendar: {from: fact_security_prices, to: temporal.dim_calendar, fk: date_id}

  paths: {}

status: active
---
```

### Layer 3: Child Model

```yaml
# domains/securities/stocks.md
---
type: domain-model
model: stocks
version: 3.1
description: "Stock equities with technicals, dividends, splits"

depends_on: [temporal, securities, company]

storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      listing_status: alpha_vantage/listing_status
      dividends: alpha_vantage/dividends
      splits: alpha_vantage/splits
  silver:
    root: storage/silver/stocks

tables:
  # Filtered dimension - stock-specific attributes
  dim_stock:
    from: bronze.alpha_vantage.listing_status
    filters:
      - "assetType = 'Stock'"
    primary_key: [stock_id]
    unique_key: [ticker]

    schema:
      - [stock_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT('STOCK_', ticker)))"}]
      - [security_id, integer, false, "FK to master", {derive: "ABS(HASH(ticker))", fk: securities.dim_security.security_id}]
      - [company_id, integer, true, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', ticker)))", fk: company.dim_company.company_id}]
      - [ticker, string, false, "Trading symbol", {from: ticker, unique: true}]
      - [security_name, string, true, "Name", {from: name}]
      - [exchange_code, string, true, "Exchange", {from: exchange}]
      - [stock_type, string, true, "Type", {derive: "'common'"}]

    measures:
      - [stock_count, count_distinct, stock_id, "Number of stocks", {format: "#,##0"}]

  # Extension - computed from master prices (post-build)
  fact_stock_technicals:
    from: computed
    description: "Computed post-build from securities.fact_security_prices"
    primary_key: [technical_id]
    partition_by: [date_id]

    schema:
      - [technical_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(security_id, '_', date_id)))"}]
      - [security_id, integer, false, "FK", {from: security_id, fk: dim_stock.security_id}]
      - [date_id, integer, false, "FK", {from: date_id, fk: temporal.dim_calendar.date_id}]
      - [sma_20, double, true, "20-day SMA", {computed: true}]
      - [sma_50, double, true, "50-day SMA", {computed: true}]
      - [sma_200, double, true, "200-day SMA", {computed: true}]
      - [rsi_14, double, true, "14-day RSI", {computed: true}]
      - [daily_return, double, true, "Daily return %", {computed: true}]
      - [volatility_20d, double, true, "20-day volatility", {computed: true}]

  # Extension - stock-specific bronze data
  fact_dividends:
    from: bronze.alpha_vantage.dividends
    primary_key: [dividend_id]
    partition_by: [ex_dividend_date_id]

    schema:
      - [dividend_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(symbol, '_', CAST(ex_dividend_date AS STRING))))"}]
      - [security_id, integer, false, "FK", {derive: "ABS(HASH(symbol))", fk: dim_stock.security_id}]
      - [ex_dividend_date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST(ex_dividend_date AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [dividend_amount, double, false, "Amount per share", {from: amount}]
      - [dividend_type, string, true, "Type", {from: type}]

    measures:
      - [total_dividends, sum, dividend_amount, "Total dividends", {format: "$#,##0.00"}]

  # Extension - stock-specific bronze data
  fact_splits:
    from: bronze.alpha_vantage.splits
    primary_key: [split_id]
    partition_by: [effective_date_id]

    schema:
      - [split_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(symbol, '_', CAST(effective_date AS STRING))))"}]
      - [security_id, integer, false, "FK", {derive: "ABS(HASH(symbol))", fk: dim_stock.security_id}]
      - [effective_date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST(effective_date AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [split_factor, double, false, "Split ratio", {from: split_factor}]

    measures:
      - [split_count, count_distinct, split_id, "Number of splits", {format: "#,##0"}]

  # NO fact_stock_prices - query securities.fact_security_prices directly

graph:
  nodes:
    dim_stock: {pk: stock_id}
    fact_stock_technicals: {pk: technical_id}
    fact_dividends: {pk: dividend_id}
    fact_splits: {pk: split_id}

  edges:
    # Cross-model edges
    stock_to_security: {from: dim_stock, to: securities.dim_security, fk: security_id}
    stock_to_company: {from: dim_stock, to: company.dim_company, fk: company_id, optional: true}
    # Internal edges
    technicals_to_stock: {from: fact_stock_technicals, to: dim_stock, fk: security_id}
    technicals_to_calendar: {from: fact_stock_technicals, to: temporal.dim_calendar, fk: date_id}
    dividends_to_stock: {from: fact_dividends, to: dim_stock, fk: security_id}
    dividends_to_calendar: {from: fact_dividends, to: temporal.dim_calendar, fk: date_id}
    splits_to_stock: {from: fact_splits, to: dim_stock, fk: security_id}
    splits_to_calendar: {from: fact_splits, to: temporal.dim_calendar, fk: date_id}

  paths:
    prices_to_sector:
      description: "Navigate from master prices to sector via stock dimension"
      via: [securities.fact_security_prices, dim_stock, company.dim_company]

status: active
---
```

### Query Example

```sql
-- Stock prices with technicals (no duplication)
SELECT
    s.ticker,
    s.security_name,
    c.date AS trade_date,
    p.open,
    p.high,
    p.low,
    p.close,
    p.volume,
    t.sma_50,
    t.rsi_14,
    co.sector,
    co.industry
FROM securities.fact_security_prices p      -- Prices from MASTER
JOIN stocks.dim_stock s
    ON p.security_id = s.security_id        -- Filter via child dimension
JOIN stocks.fact_stock_technicals t
    ON p.security_id = t.security_id
    AND p.date_id = t.date_id               -- Join extension
JOIN temporal.dim_calendar c
    ON p.date_id = c.date_id
LEFT JOIN company.dim_company co
    ON s.company_id = co.company_id
WHERE c.year = 2025
    AND s.ticker = 'AAPL'
ORDER BY c.date DESC;
```

---

## Appendix D: Financial Models (Chart of Accounts & Statements)

This appendix shows how to model financial accounting data using the unified structure.

### Financial Domain Overview

```
corporate/
├── company.md              # Company dimension (CIK-based)
├── chart_of_accounts.md    # Chart of Accounts (accounting structure)
└── financial_statements.md # Income Statement, Balance Sheet, Cash Flow
```

**Dependency Chain**:
```
temporal
    ↓
company
    ↓
chart_of_accounts
    ↓
financial_statements
```

### Model 1: Chart of Accounts

The Chart of Accounts (COA) provides the hierarchical structure for all financial line items.

```yaml
# domains/corporate/chart_of_accounts.md
---
type: domain-model
model: chart_of_accounts
version: 1.0
description: "Standard chart of accounts for financial reporting"

depends_on: [temporal]

storage:
  format: delta
  bronze:
    provider: seed
    tables:
      coa_structure: seed/chart_of_accounts
  silver:
    root: storage/silver/chart_of_accounts

tables:
  # Account Category (top level: Asset, Liability, Equity, Revenue, Expense)
  dim_account_category:
    from: seed.coa_categories
    primary_key: [category_id]
    unique_key: [category_code]

    schema:
      - [category_id, integer, false, "PK", {derive: "ABS(HASH(category_code))"}]
      - [category_code, string, false, "Code (A, L, E, R, X)", {from: code, unique: true}]
      - [category_name, string, false, "Name", {from: name}]
      - [normal_balance, string, false, "Debit or Credit", {from: normal_balance}]
      - [display_order, integer, false, "Sort order", {from: sort_order}]

    measures:
      - [category_count, count_distinct, category_id, "Number of categories", {format: "#,##0"}]

  # Account Type (sub-level: Current Assets, Fixed Assets, etc.)
  dim_account_type:
    from: seed.coa_types
    primary_key: [type_id]
    unique_key: [type_code]

    schema:
      - [type_id, integer, false, "PK", {derive: "ABS(HASH(type_code))"}]
      - [category_id, integer, false, "FK to category", {derive: "ABS(HASH(category_code))", fk: dim_account_category.category_id}]
      - [type_code, string, false, "Type code", {from: code, unique: true}]
      - [type_name, string, false, "Name", {from: name}]
      - [display_order, integer, false, "Sort order", {from: sort_order}]

    measures:
      - [type_count, count_distinct, type_id, "Number of account types", {format: "#,##0"}]

  # Account (leaf level: Cash, Accounts Receivable, Revenue, etc.)
  dim_account:
    from: seed.coa_accounts
    primary_key: [account_id]
    unique_key: [account_code]

    schema:
      - [account_id, integer, false, "PK", {derive: "ABS(HASH(account_code))"}]
      - [type_id, integer, false, "FK to type", {derive: "ABS(HASH(type_code))", fk: dim_account_type.type_id}]
      - [account_code, string, false, "Account code (e.g., 1000)", {from: code, unique: true}]
      - [account_name, string, false, "Account name", {from: name}]
      - [description, string, true, "Description", {from: description}]
      - [is_active, boolean, true, "Active account", {default: true}]
      - [gaap_mapping, string, true, "US GAAP line item", {from: gaap_mapping}]
      - [ifrs_mapping, string, true, "IFRS line item", {from: ifrs_mapping}]

    measures:
      - [account_count, count_distinct, account_id, "Number of accounts", {format: "#,##0"}]

graph:
  nodes:
    dim_account_category: {pk: category_id}
    dim_account_type: {pk: type_id}
    dim_account: {pk: account_id}

  edges:
    type_to_category: {from: dim_account_type, to: dim_account_category, fk: category_id}
    account_to_type: {from: dim_account, to: dim_account_type, fk: type_id}

  paths:
    account_hierarchy:
      description: "Account to category via type"
      via: [dim_account, dim_account_type, dim_account_category]

status: active
---

## Chart of Accounts Model

Provides the hierarchical accounting structure used by financial statements.

### Hierarchy

```
Category (5)
├── Assets (A)
│   ├── Current Assets (A-CA)
│   │   ├── 1000 - Cash
│   │   ├── 1100 - Accounts Receivable
│   │   └── 1200 - Inventory
│   └── Fixed Assets (A-FA)
│       ├── 1500 - Property & Equipment
│       └── 1600 - Accumulated Depreciation
├── Liabilities (L)
│   ├── Current Liabilities (L-CL)
│   └── Long-term Liabilities (L-LT)
├── Equity (E)
├── Revenue (R)
└── Expenses (X)
```

### Standard Account Codes

| Code Range | Category | Example |
|------------|----------|---------|
| 1000-1999 | Assets | Cash, AR, Inventory, PP&E |
| 2000-2999 | Liabilities | AP, Debt, Deferred Revenue |
| 3000-3999 | Equity | Common Stock, Retained Earnings |
| 4000-4999 | Revenue | Sales, Services, Interest Income |
| 5000-5999 | COGS | Materials, Labor, Overhead |
| 6000-6999 | Operating Expenses | SG&A, R&D, Depreciation |
| 7000-7999 | Other Income/Expense | Interest Expense, Taxes |
```

### Model 2: Financial Statements

Financial statements reference the Chart of Accounts for line item definitions.

```yaml
# domains/corporate/financial_statements.md
---
type: domain-model
model: financial_statements
version: 1.0
description: "SEC financial statements: Income, Balance Sheet, Cash Flow"

depends_on: [temporal, company, chart_of_accounts]

storage:
  format: delta
  bronze:
    provider: alpha_vantage
    tables:
      income_statement: alpha_vantage/income_statement
      balance_sheet: alpha_vantage/balance_sheet
      cash_flow: alpha_vantage/cash_flow
  silver:
    root: storage/silver/financial_statements

tables:
  # Fiscal Period dimension (quarters/years reported)
  dim_fiscal_period:
    from: bronze.alpha_vantage.income_statement
    primary_key: [fiscal_period_id]
    unique_key: [company_id, fiscal_year, fiscal_quarter]

    schema:
      - [fiscal_period_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(symbol, '_', fiscalDateEnding)))"}]
      - [company_id, integer, false, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', symbol)))", fk: company.dim_company.company_id}]
      - [period_end_date_id, integer, false, "FK to calendar", {derive: "CAST(REGEXP_REPLACE(CAST(fiscalDateEnding AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [fiscal_year, integer, false, "Fiscal year", {from: fiscalYear}]
      - [fiscal_quarter, integer, true, "Fiscal quarter (null for annual)", {from: fiscalQuarter}]
      - [report_type, string, false, "annual or quarterly", {from: reportType}]
      - [reported_currency, string, true, "Reporting currency", {from: reportedCurrency}]
      - [filing_date_id, integer, true, "SEC filing date", {derive: "CAST(REGEXP_REPLACE(CAST(filedDate AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]

    measures:
      - [period_count, count_distinct, fiscal_period_id, "Number of periods", {format: "#,##0"}]

  # Income Statement fact
  fact_income_statement:
    from: bronze.alpha_vantage.income_statement
    primary_key: [income_id]
    partition_by: [fiscal_year]

    schema:
      - [income_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(symbol, '_', fiscalDateEnding, '_income')))"}]
      - [fiscal_period_id, integer, false, "FK to period", {derive: "ABS(HASH(CONCAT(symbol, '_', fiscalDateEnding)))", fk: dim_fiscal_period.fiscal_period_id}]
      - [company_id, integer, false, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', symbol)))", fk: company.dim_company.company_id}]
      # Revenue
      - [total_revenue, long, true, "Total Revenue", {from: totalRevenue}]
      - [cost_of_revenue, long, true, "Cost of Revenue", {from: costOfRevenue}]
      - [gross_profit, long, true, "Gross Profit", {from: grossProfit}]
      # Operating
      - [operating_expenses, long, true, "Operating Expenses", {from: operatingExpenses}]
      - [operating_income, long, true, "Operating Income", {from: operatingIncome}]
      - [research_development, long, true, "R&D Expense", {from: researchAndDevelopment}]
      - [selling_general_admin, long, true, "SG&A Expense", {from: sellingGeneralAndAdministrative}]
      # Non-operating
      - [interest_expense, long, true, "Interest Expense", {from: interestExpense}]
      - [interest_income, long, true, "Interest Income", {from: interestIncome}]
      - [income_before_tax, long, true, "Income Before Tax", {from: incomeBeforeTax}]
      - [income_tax_expense, long, true, "Income Tax Expense", {from: incomeTaxExpense}]
      # Bottom line
      - [net_income, long, true, "Net Income", {from: netIncome}]
      - [ebitda, long, true, "EBITDA", {from: ebitda}]
      # Per share
      - [eps_basic, double, true, "Basic EPS", {from: basicEPS}]
      - [eps_diluted, double, true, "Diluted EPS", {from: dilutedEPS}]

    measures:
      - [avg_revenue, avg, total_revenue, "Average Revenue", {format: "$#,##0"}]
      - [avg_net_income, avg, net_income, "Average Net Income", {format: "$#,##0"}]
      - [gross_margin, expression, "AVG(gross_profit / NULLIF(total_revenue, 0) * 100)", "Gross Margin %", {format: "#,##0.00%"}]
      - [operating_margin, expression, "AVG(operating_income / NULLIF(total_revenue, 0) * 100)", "Operating Margin %", {format: "#,##0.00%"}]
      - [net_margin, expression, "AVG(net_income / NULLIF(total_revenue, 0) * 100)", "Net Margin %", {format: "#,##0.00%"}]

  # Balance Sheet fact
  fact_balance_sheet:
    from: bronze.alpha_vantage.balance_sheet
    primary_key: [balance_id]
    partition_by: [fiscal_year]

    schema:
      - [balance_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(symbol, '_', fiscalDateEnding, '_balance')))"}]
      - [fiscal_period_id, integer, false, "FK to period", {derive: "ABS(HASH(CONCAT(symbol, '_', fiscalDateEnding)))", fk: dim_fiscal_period.fiscal_period_id}]
      - [company_id, integer, false, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', symbol)))", fk: company.dim_company.company_id}]
      # Assets
      - [total_assets, long, true, "Total Assets", {from: totalAssets}]
      - [current_assets, long, true, "Current Assets", {from: totalCurrentAssets}]
      - [cash_and_equivalents, long, true, "Cash & Equivalents", {from: cashAndCashEquivalentsAtCarryingValue}]
      - [short_term_investments, long, true, "Short-term Investments", {from: shortTermInvestments}]
      - [accounts_receivable, long, true, "Accounts Receivable", {from: currentNetReceivables}]
      - [inventory, long, true, "Inventory", {from: inventory}]
      - [non_current_assets, long, true, "Non-current Assets", {from: totalNonCurrentAssets}]
      - [property_plant_equipment, long, true, "PP&E Net", {from: propertyPlantEquipment}]
      - [goodwill, long, true, "Goodwill", {from: goodwill}]
      - [intangible_assets, long, true, "Intangible Assets", {from: intangibleAssets}]
      # Liabilities
      - [total_liabilities, long, true, "Total Liabilities", {from: totalLiabilities}]
      - [current_liabilities, long, true, "Current Liabilities", {from: totalCurrentLiabilities}]
      - [accounts_payable, long, true, "Accounts Payable", {from: currentAccountsPayable}]
      - [short_term_debt, long, true, "Short-term Debt", {from: shortTermDebt}]
      - [non_current_liabilities, long, true, "Non-current Liabilities", {from: totalNonCurrentLiabilities}]
      - [long_term_debt, long, true, "Long-term Debt", {from: longTermDebt}]
      # Equity
      - [total_equity, long, true, "Total Shareholder Equity", {from: totalShareholderEquity}]
      - [common_stock, long, true, "Common Stock", {from: commonStock}]
      - [retained_earnings, long, true, "Retained Earnings", {from: retainedEarnings}]
      - [treasury_stock, long, true, "Treasury Stock", {from: treasuryStock}]

    measures:
      - [avg_total_assets, avg, total_assets, "Average Total Assets", {format: "$#,##0"}]
      - [avg_total_equity, avg, total_equity, "Average Total Equity", {format: "$#,##0"}]
      - [current_ratio, expression, "AVG(current_assets / NULLIF(current_liabilities, 0))", "Current Ratio", {format: "#,##0.00"}]
      - [debt_to_equity, expression, "AVG(total_liabilities / NULLIF(total_equity, 0))", "Debt-to-Equity", {format: "#,##0.00"}]
      - [book_value, expression, "AVG(total_equity)", "Book Value", {format: "$#,##0"}]

  # Cash Flow fact
  fact_cash_flow:
    from: bronze.alpha_vantage.cash_flow
    primary_key: [cashflow_id]
    partition_by: [fiscal_year]

    schema:
      - [cashflow_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(symbol, '_', fiscalDateEnding, '_cashflow')))"}]
      - [fiscal_period_id, integer, false, "FK to period", {derive: "ABS(HASH(CONCAT(symbol, '_', fiscalDateEnding)))", fk: dim_fiscal_period.fiscal_period_id}]
      - [company_id, integer, false, "FK to company", {derive: "ABS(HASH(CONCAT('COMPANY_', symbol)))", fk: company.dim_company.company_id}]
      # Operating Activities
      - [operating_cashflow, long, true, "Operating Cash Flow", {from: operatingCashflow}]
      - [depreciation_amortization, long, true, "D&A", {from: depreciationDepletionAndAmortization}]
      - [change_in_receivables, long, true, "Change in Receivables", {from: changeInReceivables}]
      - [change_in_inventory, long, true, "Change in Inventory", {from: changeInInventory}]
      - [change_in_payables, long, true, "Change in Payables", {from: changeInOperatingLiabilities}]
      # Investing Activities
      - [investing_cashflow, long, true, "Investing Cash Flow", {from: cashflowFromInvestment}]
      - [capital_expenditures, long, true, "CapEx", {from: capitalExpenditures}]
      - [acquisitions, long, true, "Acquisitions", {from: acquisitionsNet}]
      - [investments, long, true, "Investments", {from: investmentsInPropertyPlantAndEquipment}]
      # Financing Activities
      - [financing_cashflow, long, true, "Financing Cash Flow", {from: cashflowFromFinancing}]
      - [dividends_paid, long, true, "Dividends Paid", {from: dividendPayout}]
      - [stock_repurchase, long, true, "Stock Repurchase", {from: paymentsForRepurchaseOfCommonStock}]
      - [debt_repayment, long, true, "Debt Repayment", {from: paymentsOfDebt}]
      - [debt_proceeds, long, true, "Debt Proceeds", {from: proceedsFromIssuanceOfDebt}]
      # Net Change
      - [net_change_in_cash, long, true, "Net Change in Cash", {from: changeInCashAndCashEquivalents}]

    measures:
      - [avg_operating_cf, avg, operating_cashflow, "Average Operating CF", {format: "$#,##0"}]
      - [avg_free_cf, expression, "AVG(operating_cashflow + capital_expenditures)", "Average Free CF", {format: "$#,##0"}]
      - [capex_to_revenue, expression, "AVG(ABS(capital_expenditures) / NULLIF(total_revenue, 0) * 100)", "CapEx % of Revenue", {format: "#,##0.00%"}]

graph:
  nodes:
    dim_fiscal_period: {pk: fiscal_period_id}
    fact_income_statement: {pk: income_id}
    fact_balance_sheet: {pk: balance_id}
    fact_cash_flow: {pk: cashflow_id}

  edges:
    # Period edges
    period_to_company: {from: dim_fiscal_period, to: company.dim_company, fk: company_id}
    period_to_calendar: {from: dim_fiscal_period, to: temporal.dim_calendar, fk: period_end_date_id}
    # Income statement edges
    income_to_period: {from: fact_income_statement, to: dim_fiscal_period, fk: fiscal_period_id}
    income_to_company: {from: fact_income_statement, to: company.dim_company, fk: company_id}
    # Balance sheet edges
    balance_to_period: {from: fact_balance_sheet, to: dim_fiscal_period, fk: fiscal_period_id}
    balance_to_company: {from: fact_balance_sheet, to: company.dim_company, fk: company_id}
    # Cash flow edges
    cashflow_to_period: {from: fact_cash_flow, to: dim_fiscal_period, fk: fiscal_period_id}
    cashflow_to_company: {from: fact_cash_flow, to: company.dim_company, fk: company_id}

  paths:
    financials_to_stock:
      description: "Financial statements to stock prices via company"
      via: [fact_income_statement, company.dim_company, stocks.dim_stock, securities.fact_security_prices]

    full_financial_picture:
      description: "All three statements for a period"
      via: [dim_fiscal_period, fact_income_statement, fact_balance_sheet, fact_cash_flow]

status: active
---

## Financial Statements Model

Provides SEC financial data linked to companies and the chart of accounts.

### Statement Relationships

```
               dim_fiscal_period
              /       |        \
             /        |         \
fact_income_stmt  fact_balance  fact_cash_flow
            \         |         /
             \        |        /
          company.dim_company
                    |
            stocks.dim_stock
                    |
        securities.fact_security_prices
```

### Common Queries

```sql
-- Company financials with stock performance
SELECT
    c.company_name,
    c.sector,
    fp.fiscal_year,
    fp.fiscal_quarter,
    -- Income Statement
    i.total_revenue,
    i.net_income,
    i.eps_diluted,
    -- Balance Sheet
    b.total_assets,
    b.total_equity,
    b.cash_and_equivalents,
    -- Cash Flow
    cf.operating_cashflow,
    cf.operating_cashflow + cf.capital_expenditures AS free_cash_flow,
    -- Stock price at period end
    p.close AS period_end_price
FROM financial_statements.dim_fiscal_period fp
JOIN financial_statements.fact_income_statement i
    ON fp.fiscal_period_id = i.fiscal_period_id
JOIN financial_statements.fact_balance_sheet b
    ON fp.fiscal_period_id = b.fiscal_period_id
JOIN financial_statements.fact_cash_flow cf
    ON fp.fiscal_period_id = cf.fiscal_period_id
JOIN company.dim_company c
    ON fp.company_id = c.company_id
LEFT JOIN stocks.dim_stock s
    ON c.company_id = s.company_id
LEFT JOIN securities.fact_security_prices p
    ON s.security_id = p.security_id
    AND fp.period_end_date_id = p.date_id
WHERE c.ticker = 'AAPL'
ORDER BY fp.fiscal_year DESC, fp.fiscal_quarter DESC NULLS FIRST;
```
```

### Model 3: Financial Ratios (Computed Extension)

```yaml
# domains/corporate/financial_ratios.md
---
type: domain-model
model: financial_ratios
version: 1.0
description: "Computed financial ratios from statements"

depends_on: [temporal, company, financial_statements]

storage:
  format: delta
  silver:
    root: storage/silver/financial_ratios

tables:
  # Computed from financial_statements facts
  fact_financial_ratios:
    from: computed
    description: "Post-build computed ratios from financial statements"
    primary_key: [ratio_id]
    partition_by: [fiscal_year]

    schema:
      - [ratio_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(company_id, '_', fiscal_period_id)))"}]
      - [fiscal_period_id, integer, false, "FK", {from: fiscal_period_id, fk: financial_statements.dim_fiscal_period.fiscal_period_id}]
      - [company_id, integer, false, "FK", {from: company_id, fk: company.dim_company.company_id}]
      - [fiscal_year, integer, false, "Year", {from: fiscal_year}]

      # Profitability Ratios
      - [gross_margin, double, true, "Gross Profit / Revenue", {computed: true}]
      - [operating_margin, double, true, "Operating Income / Revenue", {computed: true}]
      - [net_margin, double, true, "Net Income / Revenue", {computed: true}]
      - [roe, double, true, "Return on Equity", {computed: true}]
      - [roa, double, true, "Return on Assets", {computed: true}]
      - [roic, double, true, "Return on Invested Capital", {computed: true}]

      # Liquidity Ratios
      - [current_ratio, double, true, "Current Assets / Current Liabilities", {computed: true}]
      - [quick_ratio, double, true, "(Current Assets - Inventory) / Current Liabilities", {computed: true}]
      - [cash_ratio, double, true, "Cash / Current Liabilities", {computed: true}]

      # Leverage Ratios
      - [debt_to_equity, double, true, "Total Debt / Total Equity", {computed: true}]
      - [debt_to_assets, double, true, "Total Debt / Total Assets", {computed: true}]
      - [interest_coverage, double, true, "EBIT / Interest Expense", {computed: true}]

      # Efficiency Ratios
      - [asset_turnover, double, true, "Revenue / Avg Assets", {computed: true}]
      - [inventory_turnover, double, true, "COGS / Avg Inventory", {computed: true}]
      - [receivable_turnover, double, true, "Revenue / Avg Receivables", {computed: true}]

      # Valuation Ratios (requires stock price)
      - [pe_ratio, double, true, "Price / EPS", {computed: true}]
      - [pb_ratio, double, true, "Price / Book Value per Share", {computed: true}]
      - [ev_to_ebitda, double, true, "Enterprise Value / EBITDA", {computed: true}]

    measures:
      - [avg_roe, avg, roe, "Average ROE", {format: "#,##0.00%"}]
      - [avg_roa, avg, roa, "Average ROA", {format: "#,##0.00%"}]
      - [avg_current_ratio, avg, current_ratio, "Average Current Ratio", {format: "#,##0.00"}]
      - [avg_debt_to_equity, avg, debt_to_equity, "Average D/E", {format: "#,##0.00"}]

graph:
  nodes:
    fact_financial_ratios: {pk: ratio_id}

  edges:
    ratios_to_period: {from: fact_financial_ratios, to: financial_statements.dim_fiscal_period, fk: fiscal_period_id}
    ratios_to_company: {from: fact_financial_ratios, to: company.dim_company, fk: company_id}

  paths:
    ratios_to_stock:
      description: "Financial ratios to stock performance"
      via: [fact_financial_ratios, company.dim_company, stocks.dim_stock, securities.fact_security_prices]

status: active
---
```

### Financial Models Summary

| Model | Type | Tables | Purpose |
|-------|------|--------|---------|
| `chart_of_accounts` | Reference | dim_account_category, dim_account_type, dim_account | Accounting structure |
| `financial_statements` | Fact | dim_fiscal_period, fact_income_statement, fact_balance_sheet, fact_cash_flow | SEC filings |
| `financial_ratios` | Computed | fact_financial_ratios | Derived metrics |

### Complete Dependency Graph

```
temporal
    │
    ├─► company
    │       │
    │       ├─► chart_of_accounts
    │       │
    │       ├─► financial_statements
    │       │       │
    │       │       └─► financial_ratios
    │       │
    │       └─► stocks ──────────────────┐
    │               │                    │
    │               └─► securities ◄─────┘
    │                       │
    └───────────────────────┘
```

### Cross-Domain Query Example

```sql
-- Full fundamental analysis: financials + ratios + stock prices
SELECT
    c.ticker,
    c.company_name,
    c.sector,
    fp.fiscal_year,
    fp.fiscal_quarter,
    -- Income metrics
    i.total_revenue / 1e9 AS revenue_bn,
    i.net_income / 1e9 AS net_income_bn,
    i.eps_diluted,
    -- Balance sheet metrics
    b.cash_and_equivalents / 1e9 AS cash_bn,
    b.total_debt / 1e9 AS debt_bn,
    -- Ratios
    r.roe,
    r.current_ratio,
    r.debt_to_equity,
    r.pe_ratio,
    -- Stock data
    cal.date AS period_end_date,
    p.close AS stock_price,
    t.rsi_14,
    t.sma_50
FROM financial_statements.dim_fiscal_period fp
JOIN financial_statements.fact_income_statement i USING (fiscal_period_id)
JOIN financial_statements.fact_balance_sheet b USING (fiscal_period_id)
JOIN financial_ratios.fact_financial_ratios r USING (fiscal_period_id)
JOIN company.dim_company c ON fp.company_id = c.company_id
JOIN temporal.dim_calendar cal ON fp.period_end_date_id = cal.date_id
LEFT JOIN stocks.dim_stock s ON c.company_id = s.company_id
LEFT JOIN securities.fact_security_prices p
    ON s.security_id = p.security_id AND fp.period_end_date_id = p.date_id
LEFT JOIN stocks.fact_stock_technicals t
    ON p.security_id = t.security_id AND p.date_id = t.date_id
WHERE c.ticker = 'AAPL'
    AND fp.report_type = 'quarterly'
ORDER BY fp.fiscal_year DESC, fp.fiscal_quarter DESC
LIMIT 8;  -- Last 2 years quarterly
```

---

## Appendix E: Entity Templates & Views

This appendix defines reusable entity templates and the views specification for creating virtual tables.

### Entity Templates Overview

Entity templates provide standardized patterns for common domain objects. They live in `domains/_base/entities/` and can be extended by any domain model.

```
domains/_base/
├── entities/                # Reusable entity templates
│   ├── entity.md           # BASE - common fields for ALL entities
│   ├── person.md           # Individual/person (extends entity)
│   ├── organization.md     # Organization/company (extends entity)
│   ├── location.md         # Geographic/address (extends entity)
│   ├── product.md          # Product/item (extends entity)
│   ├── transaction.md      # Financial transaction (extends entity)
│   └── event.md            # Time-bound event (extends entity)
├── temporal/
│   └── calendar.md
└── finance/
    └── securities.md
```

### Entity Inheritance Hierarchy

```
_base.entities.entity (common fields)
    │
    ├── _base.entities.person
    │       └── hr.dim_employee
    │       └── crm.dim_customer
    │
    ├── _base.entities.organization
    │       └── corporate.dim_company
    │       └── crm.dim_account
    │
    ├── _base.entities.location
    │       └── retail.dim_store
    │       └── logistics.dim_warehouse
    │
    ├── _base.entities.product
    │       └── retail.dim_product
    │       └── inventory.dim_item
    │
    ├── _base.entities.transaction
    │       └── sales.fact_orders
    │       └── accounting.fact_journal_entries
    │
    └── _base.entities.event
            └── operations.fact_incidents
            └── marketing.fact_campaigns
```

---

### Entity Base Template (Root)

All entity templates extend from this base, providing common audit, tracking, and status fields.

```yaml
# domains/_base/entities/entity.md
---
type: domain-base
base_name: entity
description: "Root template for all entities - provides common audit and tracking fields"

tables:
  # Base dimension - extended by all entity types
  _dim_entity:
    type: dimension
    primary_key: [entity_id]

    schema:
      # === IDENTITY ===
      # Primary key - integer surrogate (child overrides derivation)
      - [entity_id, integer, false, "PK - surrogate key"]

      # External identifiers
      - [external_id, string, true, "External system ID", {unique: true}]
      - [source_system, string, true, "Originating system name"]
      - [source_id, string, true, "ID in source system"]

      # === AUDIT FIELDS ===
      # Creation tracking
      - [created_date_id, integer, true, "FK - creation date", {fk: temporal.dim_calendar.date_id}]
      - [created_timestamp, timestamp, true, "Exact creation time"]
      - [created_by, string, true, "User/process that created"]

      # Modification tracking
      - [modified_date_id, integer, true, "FK - last modified date", {fk: temporal.dim_calendar.date_id}]
      - [modified_timestamp, timestamp, true, "Exact modification time"]
      - [modified_by, string, true, "User/process that modified"]

      # === STATUS ===
      - [is_active, boolean, true, "Record is active", {default: true}]
      - [is_deleted, boolean, true, "Soft delete flag", {default: false}]
      - [status, string, true, "Entity status", {default: "active", enum: [active, inactive, pending, archived]}]

      # === VERSIONING (Optional - for SCD Type 2) ===
      - [version, integer, true, "Record version number", {default: 1}]
      - [valid_from_date_id, integer, true, "FK - version start", {fk: temporal.dim_calendar.date_id}]
      - [valid_to_date_id, integer, true, "FK - version end (null=current)", {fk: temporal.dim_calendar.date_id}]
      - [is_current, boolean, true, "Current version flag", {default: true}]

      # === METADATA ===
      - [tags, string, true, "Comma-separated tags"]
      - [notes, string, true, "Free-form notes"]

    measures:
      - [entity_count, count_distinct, entity_id, "Total entities", {format: "#,##0"}]
      - [active_count, count_distinct, entity_id, "Active entities", {format: "#,##0", filter: "is_active = true"}]
      - [inactive_count, count_distinct, entity_id, "Inactive entities", {format: "#,##0", filter: "is_active = false"}]

  # Base fact - extended by transactional entity types
  _fact_entity_event:
    type: fact
    primary_key: [event_id]
    partition_by: [event_date_id]

    schema:
      # === IDENTITY ===
      - [event_id, integer, false, "PK - surrogate key"]
      - [entity_id, integer, false, "FK to entity", {fk: _dim_entity.entity_id}]

      # === TEMPORAL ===
      - [event_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [event_timestamp, timestamp, true, "Exact event time"]

      # === AUDIT ===
      - [source_system, string, true, "Originating system"]
      - [source_id, string, true, "ID in source system"]
      - [created_timestamp, timestamp, true, "Record creation time"]

    measures:
      - [event_count, count_distinct, event_id, "Total events", {format: "#,##0"}]

status: active
---

## Entity Base Template

The root template providing common fields for ALL entities in the system.

### Inherited Fields

Every entity that extends `_base.entities.entity` automatically gets:

| Category | Fields |
|----------|--------|
| **Identity** | entity_id, external_id, source_system, source_id |
| **Audit** | created_date_id, created_timestamp, created_by, modified_date_id, modified_timestamp, modified_by |
| **Status** | is_active, is_deleted, status |
| **Versioning** | version, valid_from_date_id, valid_to_date_id, is_current |
| **Metadata** | tags, notes |

### Usage

Child entity templates extend this base:

```yaml
# domains/_base/entities/person.md
type: domain-base
base_name: person
extends: _base.entities.entity  # Inherit common fields

tables:
  _dim_person:
    extends: _base.entities.entity._dim_entity
    # Inherits: entity_id, external_id, audit fields, status, versioning
    schema:
      # Override PK with person-specific name
      - [person_id, integer, false, "PK", {derive: "ABS(HASH(external_id))"}]
      # Add person-specific fields
      - [first_name, string, true, "First name"]
      - [last_name, string, true, "Last name"]
      # ... person-specific fields
```

### SCD Type 2 Support

The versioning fields enable Slowly Changing Dimension Type 2:

```sql
-- Get current version of entity
SELECT * FROM dim_customer
WHERE is_current = true;

-- Get entity as of specific date
SELECT * FROM dim_customer
WHERE valid_from_date_id <= 20250115
  AND (valid_to_date_id IS NULL OR valid_to_date_id > 20250115);

-- Get all versions of an entity
SELECT * FROM dim_customer
WHERE external_id = 'CUST-12345'
ORDER BY version;
```
```

---

### Entity Template 1: Person

```yaml
# domains/_base/entities/person.md
---
type: domain-base
base_name: person
description: "Base template for individual/person entities"

# Inherit common fields from entity base
extends: _base.entities.entity

tables:
  _dim_person:
    type: dimension
    extends: _base.entities.entity._dim_entity  # Inherit audit, status, versioning
    primary_key: [person_id]

    schema:
      # === IDENTITY (override entity_id with person_id) ===
      - [person_id, integer, false, "PK - surrogate"]
      # external_id, source_system, source_id inherited from entity

      # === NAME COMPONENTS (person-specific) ===
      - [first_name, string, true, "First/given name"]
      - [middle_name, string, true, "Middle name"]
      - [last_name, string, true, "Last/family name"]
      - [full_name, string, true, "Computed full name"]
      - [display_name, string, true, "Preferred display name"]
      - [name_prefix, string, true, "Mr, Ms, Dr, etc."]
      - [name_suffix, string, true, "Jr, Sr, III, PhD, etc."]

      # === CONTACT (person-specific) ===
      - [email, string, true, "Primary email"]
      - [phone, string, true, "Primary phone"]
      - [mobile, string, true, "Mobile phone"]

      # === DEMOGRAPHICS (person-specific) ===
      - [birth_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [gender, string, true, "Gender identity"]
      - [nationality, string, true, "Nationality/citizenship"]
      - [language, string, true, "Preferred language"]

      # === INHERITED FROM ENTITY (for reference) ===
      # - is_active, is_deleted, status (from entity)
      # - created_date_id, created_timestamp, created_by (from entity)
      # - modified_date_id, modified_timestamp, modified_by (from entity)
      # - version, valid_from_date_id, valid_to_date_id, is_current (from entity)
      # - tags, notes (from entity)

    measures:
      - [person_count, count_distinct, person_id, "Number of persons", {format: "#,##0"}]
      # active_count, inactive_count inherited from entity

status: active
---

## Person Entity Template

Standard template for representing individuals across domains.

### Inherited from Entity Base

| Field | Source |
|-------|--------|
| external_id, source_system, source_id | `_base.entities.entity` |
| is_active, is_deleted, status | `_base.entities.entity` |
| created_*, modified_* | `_base.entities.entity` |
| version, valid_from/to, is_current | `_base.entities.entity` |
| tags, notes | `_base.entities.entity` |

### Person-Specific Fields

| Field | Description |
|-------|-------------|
| first_name, middle_name, last_name | Name components |
| full_name, display_name | Computed/preferred names |
| name_prefix, name_suffix | Mr/Ms/Dr, Jr/Sr/III |
| email, phone, mobile | Contact info |
| birth_date_id, gender | Demographics |

### Common Extensions

| Domain | Extension | Added Fields |
|--------|-----------|--------------|
| HR | Employee | employee_id, hire_date, department_id, manager_id, salary |
| CRM | Customer | customer_id, account_id, lifetime_value, segment |
| Healthcare | Patient | patient_id, mrn, insurance_id, primary_care_provider |
| Education | Student | student_id, enrollment_date, gpa, major |
```

### Entity Template 2: Organization

```yaml
# domains/_base/entities/organization.md
---
type: domain-base
base_name: organization
description: "Base template for organization/company entities"

# Inherit common fields from entity base
extends: _base.entities.entity

tables:
  _dim_organization:
    type: dimension
    extends: _base.entities.entity._dim_entity  # Inherit audit, status, versioning
    primary_key: [org_id]

    schema:
      # === IDENTITY (override entity_id with org_id) ===
      - [org_id, integer, false, "PK - surrogate"]
      # external_id, source_system, source_id inherited from entity
      - [tax_id, string, true, "Tax identification number (EIN)"]
      - [duns_number, string, true, "D-U-N-S Number"]

      # === NAME (organization-specific) ===
      - [org_name, string, false, "Legal name"]
      - [dba_name, string, true, "Doing business as"]
      - [short_name, string, true, "Abbreviated name"]
      - [legal_form, string, true, "Inc, LLC, Corp, Ltd, etc."]

      # === CLASSIFICATION (organization-specific) ===
      - [org_type, string, true, "Corporation, LLC, Partnership, etc."]
      - [industry_code, string, true, "Industry classification (NAICS/SIC)"]
      - [sector, string, true, "Business sector"]
      - [sub_sector, string, true, "Business sub-sector"]
      - [employee_count_range, string, true, "1-10, 11-50, 51-200, etc."]
      - [revenue_range, string, true, "Revenue band"]

      # === HIERARCHY (organization-specific) ===
      - [parent_org_id, integer, true, "FK to parent org (self-ref)"]
      - [ultimate_parent_org_id, integer, true, "FK to ultimate parent"]
      - [hierarchy_level, integer, true, "Depth in org tree (0=root)"]
      - [hierarchy_path, string, true, "Full path: /root/parent/child"]

      # === CONTACT (organization-specific) ===
      - [website, string, true, "Primary website"]
      - [phone, string, true, "Main phone"]
      - [email, string, true, "Main contact email"]

      # === DATES (organization-specific) ===
      - [founded_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [incorporated_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [dissolved_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]

      # === INHERITED FROM ENTITY ===
      # - is_active, is_deleted, status, version, valid_from/to, is_current
      # - created_*, modified_*, tags, notes

    measures:
      - [org_count, count_distinct, org_id, "Number of organizations", {format: "#,##0"}]
      - [subsidiary_count, count_distinct, org_id, "Subsidiaries", {format: "#,##0", filter: "parent_org_id IS NOT NULL"}]
      - [root_count, count_distinct, org_id, "Parent orgs", {format: "#,##0", filter: "parent_org_id IS NULL"}]

  # Self-referential closure table for hierarchy queries
  _fact_org_hierarchy:
    type: fact
    extends: _base.entities.entity._fact_entity_event
    description: "Flattened org hierarchy for efficient queries"
    primary_key: [hierarchy_id]

    schema:
      - [hierarchy_id, integer, false, "PK"]
      - [ancestor_org_id, integer, false, "FK to ancestor", {fk: _dim_organization.org_id}]
      - [descendant_org_id, integer, false, "FK to descendant", {fk: _dim_organization.org_id}]
      - [depth, integer, false, "Levels between ancestor and descendant"]
      - [is_direct, boolean, false, "Direct parent-child relationship"]
      - [relationship_type, string, true, "Ownership, Division, Subsidiary, etc."]

status: active
---

## Organization Entity Template

### Inherited from Entity Base

All audit, status, and versioning fields from `_base.entities.entity`.

### Organization-Specific Fields

| Category | Fields |
|----------|--------|
| Identity | org_id, tax_id, duns_number |
| Name | org_name, dba_name, short_name, legal_form |
| Classification | org_type, industry_code, sector, employee/revenue ranges |
| Hierarchy | parent_org_id, ultimate_parent_org_id, hierarchy_level, hierarchy_path |
| Contact | website, phone, email |
| Dates | founded_date_id, incorporated_date_id, dissolved_date_id |

### Hierarchy Queries

```sql
-- Get all subsidiaries of an org (any depth)
SELECT d.org_name, h.depth
FROM fact_org_hierarchy h
JOIN dim_organization d ON h.descendant_org_id = d.org_id
WHERE h.ancestor_org_id = 12345
  AND h.depth > 0
ORDER BY h.depth, d.org_name;

-- Get full path to root
SELECT a.org_name, h.depth
FROM fact_org_hierarchy h
JOIN dim_organization a ON h.ancestor_org_id = a.org_id
WHERE h.descendant_org_id = 12345
ORDER BY h.depth DESC;
```
```

### Entity Template 3: Location

```yaml
# domains/_base/entities/location.md
---
type: domain-base
base_name: location
description: "Base template for geographic/address entities"

extends: _base.entities.entity

tables:
  _dim_location:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [location_id]

    schema:
      # === IDENTITY ===
      - [location_id, integer, false, "PK - surrogate"]
      - [location_code, string, true, "Business location code", {unique: true}]

      # === ADDRESS COMPONENTS ===
      - [address_line_1, string, true, "Street address"]
      - [address_line_2, string, true, "Suite, unit, etc."]
      - [city, string, true, "City/municipality"]
      - [state_province, string, true, "State/province/region"]
      - [postal_code, string, true, "ZIP/postal code"]
      - [country_code, string, true, "ISO 3166-1 alpha-2"]
      - [country_name, string, true, "Full country name"]

      # === FORMATTED ===
      - [full_address, string, true, "Complete formatted address"]
      - [short_address, string, true, "City, State format"]

      # === GEOCODING ===
      - [latitude, double, true, "Latitude coordinate"]
      - [longitude, double, true, "Longitude coordinate"]
      - [geohash, string, true, "Geohash for spatial indexing"]
      - [timezone, string, true, "IANA timezone"]

      # === CLASSIFICATION ===
      - [location_type, string, true, "Physical, Virtual, PO Box, etc."]
      - [is_verified, boolean, true, "Address verified", {default: false}]

      # === ADMINISTRATIVE REGIONS ===
      - [region, string, true, "Business region"]
      - [district, string, true, "District/area"]
      - [territory, string, true, "Sales territory"]

      # Inherits: audit, status, versioning from entity

    measures:
      - [location_count, count_distinct, location_id, "Number of locations", {format: "#,##0"}]
      - [verified_count, count_distinct, location_id, "Verified locations", {format: "#,##0", filter: "is_verified = true"}]

status: active
---
```

### Entity Template 4: Product

```yaml
# domains/_base/entities/product.md
---
type: domain-base
base_name: product
description: "Base template for product/item entities"

extends: _base.entities.entity

tables:
  _dim_product:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [product_id]

    schema:
      # === IDENTITY ===
      - [product_id, integer, false, "PK - surrogate"]
      - [sku, string, false, "Stock keeping unit", {unique: true}]
      - [upc, string, true, "Universal product code"]
      - [gtin, string, true, "Global Trade Item Number"]

      # === DESCRIPTION ===
      - [product_name, string, false, "Product name"]
      - [short_description, string, true, "Brief description"]
      - [long_description, string, true, "Full description"]

      # === CLASSIFICATION ===
      - [category_id, integer, true, "FK to category", {fk: _dim_product_category.category_id}]
      - [brand, string, true, "Brand name"]
      - [manufacturer, string, true, "Manufacturer"]
      - [product_type, string, true, "Physical, Digital, Service"]

      # === PRICING ===
      - [unit_cost, double, true, "Cost per unit"]
      - [list_price, double, true, "List/MSRP price"]
      - [currency, string, true, "Price currency", {default: "USD"}]

      # === PHYSICAL ATTRIBUTES ===
      - [weight, double, true, "Weight in standard unit"]
      - [weight_unit, string, true, "kg, lb, oz, etc."]
      - [length, double, true, "Length"]
      - [width, double, true, "Width"]
      - [height, double, true, "Height"]
      - [dimension_unit, string, true, "cm, in, etc."]

      # === LIFECYCLE ===
      - [launch_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [discontinue_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]

      # Inherits: audit, status, versioning from entity

    measures:
      - [product_count, count_distinct, product_id, "Number of products", {format: "#,##0"}]
      - [avg_list_price, avg, list_price, "Average list price", {format: "$#,##0.00"}]
      - [avg_margin, expression, "AVG((list_price - unit_cost) / NULLIF(list_price, 0) * 100)", "Average margin %", {format: "#,##0.00%"}]

  _dim_product_category:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [category_id]

    schema:
      - [category_id, integer, false, "PK"]
      - [category_code, string, false, "Category code", {unique: true}]
      - [category_name, string, false, "Category name"]
      - [parent_category_id, integer, true, "FK to parent (self-ref)"]
      - [hierarchy_level, integer, true, "Depth in category tree"]
      - [hierarchy_path, string, true, "Full path"]

status: active
---
```

### Entity Template 5: Transaction

```yaml
# domains/_base/entities/transaction.md
---
type: domain-base
base_name: transaction
description: "Base template for financial transaction entities"

extends: _base.entities.entity

tables:
  _fact_transaction:
    type: fact
    extends: _base.entities.entity._fact_entity_event
    primary_key: [transaction_id]
    partition_by: [transaction_date_id]

    schema:
      # === IDENTITY ===
      - [transaction_id, integer, false, "PK - surrogate"]
      - [transaction_number, string, false, "Business transaction ID", {unique: true}]
      - [external_ref, string, true, "External reference"]

      # === TEMPORAL ===
      - [transaction_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [transaction_timestamp, timestamp, true, "Exact timestamp"]
      - [posted_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]

      # === CLASSIFICATION ===
      - [transaction_type, string, false, "Sale, Return, Adjustment, etc."]
      - [transaction_status, string, false, "Pending, Complete, Cancelled"]
      - [channel, string, true, "Online, Store, Phone, etc."]

      # === AMOUNTS ===
      - [gross_amount, double, false, "Gross transaction amount"]
      - [discount_amount, double, true, "Discount applied"]
      - [tax_amount, double, true, "Tax amount"]
      - [net_amount, double, false, "Net transaction amount"]
      - [currency, string, false, "Transaction currency", {default: "USD"}]

      # === FOREIGN KEYS (mapped by child) ===
      - [customer_id, integer, true, "FK to customer/person"]
      - [location_id, integer, true, "FK to location"]
      - [employee_id, integer, true, "FK to employee"]

      # Inherits: source_system, source_id, created_timestamp from entity

    measures:
      - [transaction_count, count_distinct, transaction_id, "Number of transactions", {format: "#,##0"}]
      - [total_gross, sum, gross_amount, "Total gross", {format: "$#,##0.00"}]
      - [total_net, sum, net_amount, "Total net", {format: "$#,##0.00"}]
      - [avg_transaction, avg, net_amount, "Average transaction", {format: "$#,##0.00"}]
      - [total_discount, sum, discount_amount, "Total discounts", {format: "$#,##0.00"}]
      - [discount_rate, expression, "SUM(discount_amount) / NULLIF(SUM(gross_amount), 0) * 100", "Discount rate %", {format: "#,##0.00%"}]

  _fact_transaction_line:
    type: fact
    primary_key: [line_id]

    schema:
      - [line_id, integer, false, "PK"]
      - [transaction_id, integer, false, "FK to transaction", {fk: _fact_transaction.transaction_id}]
      - [line_number, integer, false, "Line sequence"]
      - [product_id, integer, true, "FK to product"]
      - [quantity, double, false, "Quantity"]
      - [unit_price, double, false, "Price per unit"]
      - [line_amount, double, false, "Line total"]
      - [discount_amount, double, true, "Line discount"]
      - [tax_amount, double, true, "Line tax"]

    measures:
      - [line_count, count_distinct, line_id, "Number of lines", {format: "#,##0"}]
      - [total_quantity, sum, quantity, "Total quantity", {format: "#,##0"}]
      - [total_line_amount, sum, line_amount, "Total line amount", {format: "$#,##0.00"}]

status: active
---
```

### Entity Template 6: Event

```yaml
# domains/_base/entities/event.md
---
type: domain-base
base_name: event
description: "Base template for time-bound event entities"

extends: _base.entities.entity

tables:
  _dim_event_type:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [event_type_id]

    schema:
      - [event_type_id, integer, false, "PK"]
      - [event_type_code, string, false, "Type code", {unique: true}]
      - [event_type_name, string, false, "Type name"]
      - [event_category, string, true, "Category grouping"]
      - [severity_level, string, true, "Info, Warning, Critical, etc."]
      - [is_actionable, boolean, true, "Requires response", {default: false}]
      - [sla_minutes, integer, true, "SLA for resolution"]

      # Inherits: audit, status, versioning from entity

  _fact_event:
    type: fact
    extends: _base.entities.entity._fact_entity_event
    primary_key: [event_id]
    partition_by: [event_date_id]

    schema:
      # === IDENTITY ===
      - [event_id, integer, false, "PK - surrogate"]
      - [event_key, string, false, "Business event key", {unique: true}]

      # === TEMPORAL ===
      - [event_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [event_timestamp, timestamp, false, "Exact event time"]
      - [end_timestamp, timestamp, true, "Event end time"]
      - [duration_seconds, long, true, "Event duration"]

      # === CLASSIFICATION ===
      - [event_type_id, integer, false, "FK to event type", {fk: _dim_event_type.event_type_id}]
      - [event_status, string, true, "Open, Acknowledged, Resolved"]
      - [priority, string, true, "Low, Medium, High, Critical"]

      # === CONTEXT ===
      - [source_entity_type, string, true, "Entity type that triggered"]
      - [source_entity_id, string, true, "Entity ID that triggered"]
      - [related_entity_type, string, true, "Related entity type"]
      - [related_entity_id, string, true, "Related entity ID"]

      # === CONTENT ===
      - [event_title, string, true, "Short title"]
      - [event_description, string, true, "Full description"]
      - [event_data, string, true, "JSON payload"]

      # === RESOLUTION ===
      - [resolved_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [resolved_timestamp, timestamp, true, "Resolution time"]
      - [resolved_by, string, true, "User/process that resolved"]
      - [resolution_notes, string, true, "Resolution notes"]

      # Inherits: source_system, source_id, created_timestamp from entity

    measures:
      - [event_count, count_distinct, event_id, "Number of events", {format: "#,##0"}]
      - [critical_count, count_distinct, event_id, "Critical events", {format: "#,##0", filter: "priority = 'Critical'"}]
      - [open_count, count_distinct, event_id, "Open events", {format: "#,##0", filter: "event_status = 'Open'"}]
      - [avg_duration, avg, duration_seconds, "Average duration (s)", {format: "#,##0"}]
      - [avg_resolution_time, expression, "AVG(TIMESTAMPDIFF(MINUTE, event_timestamp, resolved_timestamp))", "Avg resolution (min)", {format: "#,##0"}]

status: active
---
```

---

## Views Specification

Views define virtual tables that are not materialized but computed at query time. They provide:
- Pre-joined denormalized datasets
- Aggregated summaries
- Filtered subsets
- Calculated fields

### View Definition Syntax

Views are defined in the `views:` section of a domain model.

```yaml
type: domain-model
model: example

tables:
  # ... table definitions ...

views:
  # Simple view - select from single table with filter
  vw_active_customers:
    description: "Active customers only"
    from: dim_customer
    filters:
      - "is_active = true"
    columns:
      - customer_id
      - full_name
      - email
      - created_date_id

  # Join view - denormalized for easy querying
  vw_orders_denorm:
    description: "Orders with customer and product details"
    from: fact_orders
    joins:
      - {table: dim_customer, on: "customer_id", type: inner}
      - {table: dim_product, on: "product_id", type: inner}
      - {table: temporal.dim_calendar, on: "order_date_id = date_id", type: inner}
    columns:
      # From fact
      - order_id
      - order_amount
      # From dim_customer (aliased)
      - {column: dim_customer.full_name, as: customer_name}
      - {column: dim_customer.email, as: customer_email}
      # From dim_product
      - {column: dim_product.product_name, as: product}
      # From calendar
      - {column: dim_calendar.date, as: order_date}
      - {column: dim_calendar.year, as: order_year}
      - {column: dim_calendar.month_name, as: order_month}

  # Aggregate view - summary statistics
  vw_monthly_sales:
    description: "Monthly sales summary"
    from: fact_orders
    joins:
      - {table: temporal.dim_calendar, on: "order_date_id = date_id", type: inner}
    group_by:
      - dim_calendar.year
      - dim_calendar.month
      - dim_calendar.month_name
    columns:
      - {column: dim_calendar.year, as: year}
      - {column: dim_calendar.month, as: month}
      - {column: dim_calendar.month_name, as: month_name}
      - {column: "COUNT(DISTINCT order_id)", as: order_count}
      - {column: "SUM(order_amount)", as: total_sales}
      - {column: "AVG(order_amount)", as: avg_order}
      - {column: "COUNT(DISTINCT customer_id)", as: unique_customers}

  # Calculated view - derived fields
  vw_customer_metrics:
    description: "Customer lifetime metrics"
    from: dim_customer
    joins:
      - {table: fact_orders, on: "customer_id", type: left, alias: o}
    group_by:
      - dim_customer.customer_id
      - dim_customer.full_name
      - dim_customer.email
    columns:
      - customer_id
      - full_name
      - email
      - {column: "COUNT(o.order_id)", as: total_orders}
      - {column: "SUM(o.order_amount)", as: lifetime_value}
      - {column: "AVG(o.order_amount)", as: avg_order_value}
      - {column: "MIN(o.order_date_id)", as: first_order_date_id}
      - {column: "MAX(o.order_date_id)", as: last_order_date_id}
      - {column: "DATEDIFF(MAX(o.order_date_id), MIN(o.order_date_id))", as: customer_tenure_days}

graph:
  nodes:
    # ... regular nodes ...
    # Views appear as virtual nodes
    vw_active_customers: {pk: customer_id, type: view}
    vw_orders_denorm: {pk: order_id, type: view}
    vw_monthly_sales: {pk: [year, month], type: view}
    vw_customer_metrics: {pk: customer_id, type: view}

  edges:
    # Views can participate in edges
    # ...
```

### View Types

| Type | Purpose | Example |
|------|---------|---------|
| **Filter View** | Subset of rows | Active customers, recent orders |
| **Join View** | Denormalized data | Order + customer + product |
| **Aggregate View** | Grouped summaries | Monthly totals, YTD metrics |
| **Calculated View** | Derived fields | Lifetime value, running totals |
| **Union View** | Combined datasets | All transactions from multiple sources |

### Complete Views Example

```yaml
# domains/retail/sales.md
---
type: domain-model
model: sales
depends_on: [temporal, customers, products, locations]

storage:
  format: delta
  silver:
    root: storage/silver/sales

tables:
  fact_orders:
    from: bronze.pos.orders
    primary_key: [order_id]
    partition_by: [order_date_id]

    schema:
      - [order_id, integer, false, "PK", {derive: "ABS(HASH(order_number))"}]
      - [order_number, string, false, "Business order ID", {from: order_num, unique: true}]
      - [customer_id, integer, false, "FK", {derive: "ABS(HASH(customer_code))", fk: customers.dim_customer.customer_id}]
      - [location_id, integer, false, "FK", {derive: "ABS(HASH(store_code))", fk: locations.dim_location.location_id}]
      - [order_date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST(order_date AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      - [order_amount, double, false, "Order total", {from: total_amount}]
      - [discount_amount, double, true, "Discount", {from: discount}]
      - [tax_amount, double, true, "Tax", {from: tax}]
      - [order_status, string, false, "Status", {from: status}]

    measures:
      - [order_count, count_distinct, order_id, "Orders", {format: "#,##0"}]
      - [total_revenue, sum, order_amount, "Revenue", {format: "$#,##0.00"}]

  fact_order_lines:
    from: bronze.pos.order_lines
    primary_key: [line_id]

    schema:
      - [line_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT(order_number, '_', line_num)))"}]
      - [order_id, integer, false, "FK", {derive: "ABS(HASH(order_number))", fk: fact_orders.order_id}]
      - [product_id, integer, false, "FK", {derive: "ABS(HASH(sku))", fk: products.dim_product.product_id}]
      - [quantity, integer, false, "Qty", {from: qty}]
      - [unit_price, double, false, "Price", {from: price}]
      - [line_total, double, false, "Total", {derive: "qty * price"}]

views:
  # Filter view - recent completed orders
  vw_recent_orders:
    description: "Completed orders from last 90 days"
    from: fact_orders
    filters:
      - "order_status = 'completed'"
      - "order_date_id >= CAST(DATE_FORMAT(DATE_SUB(CURRENT_DATE(), 90), 'yyyyMMdd') AS INT)"
    columns:
      - order_id
      - order_number
      - customer_id
      - location_id
      - order_date_id
      - order_amount

  # Join view - orders with full context
  vw_orders_full:
    description: "Orders denormalized with customer, location, calendar"
    from: fact_orders
    joins:
      - {table: customers.dim_customer, on: "customer_id", type: inner, alias: c}
      - {table: locations.dim_location, on: "location_id", type: inner, alias: l}
      - {table: temporal.dim_calendar, on: "order_date_id = date_id", type: inner, alias: cal}
    columns:
      # Order fields
      - order_id
      - order_number
      - order_amount
      - discount_amount
      - order_status
      # Customer fields
      - {column: c.customer_id, as: customer_id}
      - {column: c.full_name, as: customer_name}
      - {column: c.email, as: customer_email}
      - {column: c.customer_segment, as: segment}
      # Location fields
      - {column: l.location_id, as: location_id}
      - {column: l.city, as: store_city}
      - {column: l.state_province, as: store_state}
      - {column: l.region, as: store_region}
      # Calendar fields
      - {column: cal.date, as: order_date}
      - {column: cal.year, as: order_year}
      - {column: cal.quarter, as: order_quarter}
      - {column: cal.month_name, as: order_month}
      - {column: cal.day_of_week_name, as: order_day}
      - {column: cal.is_weekend, as: is_weekend_order}

  # Aggregate view - daily summary
  vw_daily_sales:
    description: "Daily sales summary by location"
    from: fact_orders
    joins:
      - {table: locations.dim_location, on: "location_id", type: inner, alias: l}
      - {table: temporal.dim_calendar, on: "order_date_id = date_id", type: inner, alias: cal}
    filters:
      - "order_status = 'completed'"
    group_by:
      - cal.date_id
      - cal.date
      - cal.year
      - cal.month
      - cal.day_of_week_name
      - l.location_id
      - l.city
      - l.region
    columns:
      - {column: cal.date_id, as: date_id}
      - {column: cal.date, as: sale_date}
      - {column: cal.year, as: year}
      - {column: cal.month, as: month}
      - {column: cal.day_of_week_name, as: day_of_week}
      - {column: l.location_id, as: location_id}
      - {column: l.city, as: city}
      - {column: l.region, as: region}
      - {column: "COUNT(DISTINCT order_id)", as: order_count}
      - {column: "COUNT(DISTINCT customer_id)", as: customer_count}
      - {column: "SUM(order_amount)", as: total_sales}
      - {column: "SUM(discount_amount)", as: total_discounts}
      - {column: "AVG(order_amount)", as: avg_order_value}

  # Aggregate view - monthly summary
  vw_monthly_sales:
    description: "Monthly sales summary"
    from: fact_orders
    joins:
      - {table: temporal.dim_calendar, on: "order_date_id = date_id", type: inner, alias: cal}
    filters:
      - "order_status = 'completed'"
    group_by:
      - cal.year
      - cal.month
      - cal.month_name
      - cal.year_month
    columns:
      - {column: cal.year, as: year}
      - {column: cal.month, as: month}
      - {column: cal.month_name, as: month_name}
      - {column: cal.year_month, as: year_month}
      - {column: "COUNT(DISTINCT order_id)", as: order_count}
      - {column: "COUNT(DISTINCT customer_id)", as: unique_customers}
      - {column: "SUM(order_amount)", as: total_revenue}
      - {column: "SUM(discount_amount)", as: total_discounts}
      - {column: "AVG(order_amount)", as: avg_order_value}
      - {column: "SUM(order_amount) - SUM(discount_amount)", as: net_revenue}

  # Calculated view - customer lifetime value
  vw_customer_ltv:
    description: "Customer lifetime value and metrics"
    from: customers.dim_customer
    joins:
      - {table: fact_orders, on: "customer_id", type: left, alias: o}
      - {table: temporal.dim_calendar, on: "o.order_date_id = date_id", type: left, alias: cal}
    filters:
      - "o.order_status = 'completed' OR o.order_id IS NULL"
    group_by:
      - dim_customer.customer_id
      - dim_customer.full_name
      - dim_customer.email
      - dim_customer.customer_segment
      - dim_customer.created_date_id
    columns:
      - {column: dim_customer.customer_id, as: customer_id}
      - {column: dim_customer.full_name, as: customer_name}
      - {column: dim_customer.email, as: email}
      - {column: dim_customer.customer_segment, as: segment}
      - {column: "COUNT(DISTINCT o.order_id)", as: total_orders}
      - {column: "COALESCE(SUM(o.order_amount), 0)", as: lifetime_value}
      - {column: "COALESCE(AVG(o.order_amount), 0)", as: avg_order_value}
      - {column: "MIN(cal.date)", as: first_order_date}
      - {column: "MAX(cal.date)", as: last_order_date}
      - {column: "DATEDIFF(CURRENT_DATE(), MAX(cal.date))", as: days_since_last_order}
      - {column: "CASE WHEN COUNT(o.order_id) = 0 THEN 'Never' WHEN COUNT(o.order_id) = 1 THEN 'One-time' WHEN DATEDIFF(CURRENT_DATE(), MAX(cal.date)) > 365 THEN 'Lapsed' ELSE 'Active' END", as: customer_status}

  # Product performance view
  vw_product_performance:
    description: "Product sales performance"
    from: fact_order_lines
    joins:
      - {table: fact_orders, on: "order_id", type: inner, alias: o}
      - {table: products.dim_product, on: "product_id", type: inner, alias: p}
      - {table: temporal.dim_calendar, on: "o.order_date_id = date_id", type: inner, alias: cal}
    filters:
      - "o.order_status = 'completed'"
    group_by:
      - p.product_id
      - p.sku
      - p.product_name
      - p.category_id
      - p.brand
      - cal.year
      - cal.month
    columns:
      - {column: p.product_id, as: product_id}
      - {column: p.sku, as: sku}
      - {column: p.product_name, as: product_name}
      - {column: p.brand, as: brand}
      - {column: cal.year, as: year}
      - {column: cal.month, as: month}
      - {column: "SUM(quantity)", as: units_sold}
      - {column: "SUM(line_total)", as: total_revenue}
      - {column: "COUNT(DISTINCT o.order_id)", as: order_count}
      - {column: "AVG(unit_price)", as: avg_selling_price}

graph:
  nodes:
    fact_orders: {pk: order_id}
    fact_order_lines: {pk: line_id}
    # View nodes
    vw_recent_orders: {pk: order_id, type: view}
    vw_orders_full: {pk: order_id, type: view}
    vw_daily_sales: {pk: [date_id, location_id], type: view}
    vw_monthly_sales: {pk: year_month, type: view}
    vw_customer_ltv: {pk: customer_id, type: view}
    vw_product_performance: {pk: [product_id, year, month], type: view}

  edges:
    orders_to_customer: {from: fact_orders, to: customers.dim_customer, fk: customer_id}
    orders_to_location: {from: fact_orders, to: locations.dim_location, fk: location_id}
    orders_to_calendar: {from: fact_orders, to: temporal.dim_calendar, fk: order_date_id}
    lines_to_orders: {from: fact_order_lines, to: fact_orders, fk: order_id}
    lines_to_product: {from: fact_order_lines, to: products.dim_product, fk: product_id}

  paths:
    product_to_customer:
      description: "What customers bought what products"
      via: [products.dim_product, fact_order_lines, fact_orders, customers.dim_customer]

status: active
---

## Sales Model

Complete sales model with tables and analytical views.

### View Usage

```sql
-- Use denormalized view for simple queries
SELECT * FROM sales.vw_orders_full
WHERE order_year = 2025 AND store_region = 'West';

-- Use aggregate view for dashboards
SELECT * FROM sales.vw_monthly_sales
WHERE year = 2025
ORDER BY month;

-- Use LTV view for customer analysis
SELECT * FROM sales.vw_customer_ltv
WHERE customer_status = 'Lapsed'
ORDER BY lifetime_value DESC
LIMIT 100;
```
```

### Views Quick Reference

| Attribute | Required | Description |
|-----------|----------|-------------|
| `description` | Yes | What the view provides |
| `from` | Yes | Base table |
| `joins` | No | Tables to join |
| `filters` | No | WHERE conditions |
| `group_by` | No | GROUP BY columns (for aggregates) |
| `columns` | Yes | Output columns |

### Column Specification

```yaml
columns:
  # Simple - column from base table
  - column_name

  # Aliased - column with new name
  - {column: source.column, as: alias}

  # Calculated - expression
  - {column: "SUM(amount)", as: total}
  - {column: "CASE WHEN x > 0 THEN 'Yes' ELSE 'No' END", as: flag}
```

### Join Specification

```yaml
joins:
  # Simple join on matching column name
  - {table: dim_customer, on: "customer_id", type: inner}

  # Join with different column names
  - {table: dim_calendar, on: "order_date_id = date_id", type: inner}

  # Join with alias
  - {table: fact_orders, on: "customer_id", type: left, alias: o}
```

| Join Type | Description |
|-----------|-------------|
| `inner` | Only matching rows |
| `left` | All from base + matching |
| `right` | All from joined + matching |
| `full` | All from both |

---

## Appendix F: YAML Template Master Reference

Copy-paste templates for all domain model components.

---

### F.1 Domain Base Template (Not Built)

```yaml
# domains/_base/{category}/{name}.md
---
type: domain-base
base_name: {template_name}
description: "{Brief description of what this template provides}"

# Optional: declare dependencies on other templates
depends_on: []

tables:
  # Dimension template (prefix with _ for templates)
  _dim_{name}:
    type: dimension
    # NO 'from:' in templates - child provides data source
    primary_key: [{pk_column}]
    unique_key: [{natural_key}]  # Optional

    schema:
      # [column_name, type, nullable, description, {options}]
      - [{pk_column}, integer, false, "PK - surrogate"]
      - [{natural_key}, string, false, "Natural key", {unique: true}]
      - [{attribute}, string, true, "Description"]

    measures:
      # [name, aggregation, column, description, {options}]
      - [{name}_count, count_distinct, {pk_column}, "Count", {format: "#,##0"}]

  # Fact template
  _fact_{name}:
    type: fact
    # NO 'from:' in templates
    primary_key: [{pk_column}]
    partition_by: [date_id]

    schema:
      - [{pk_column}, integer, false, "PK - surrogate"]
      - [{dim_fk}, integer, false, "FK to dimension", {fk: _dim_{name}.{pk}}]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [{measure_col}, double, true, "Measure description"]

    measures:
      - [total_{measure}, sum, {measure_col}, "Total", {format: "#,##0.00"}]

# NO graph section in templates - child defines relationships
status: active
---

## {Template Name} Template

Documentation for this template.

### Usage

```yaml
extends: _base.{category}.{template_name}
```

### Columns Provided

| Column | Type | Description |
|--------|------|-------------|
| ... | ... | ... |
```

---

### F.2 Domain Model Template (Built)

```yaml
# domains/{category}/{model}.md
---
type: domain-model
model: {model_name}
version: 1.0
description: "{Brief description}"

# Optional: inherit schema from base template
extends: _base.{category}.{template_name}

# Build order dependencies
depends_on: [temporal]  # Add others as needed

# Storage configuration
storage:
  format: delta
  bronze:
    provider: {provider_name}
    tables:
      {table_name}: {provider}/{table_path}
  silver:
    root: storage/silver/{model_name}

# Build configuration (optional)
build:
  partitions: [date_id]
  sort_by: [{pk_column}]
  optimize: true

# Table definitions
tables:
  dim_{name}:
    type: dimension
    from: bronze.{provider}.{table}
    filters:
      - "{filter_condition}"
    primary_key: [{pk_column}]
    unique_key: [{natural_key}]

    schema:
      # Keys
      - [{pk_column}, integer, false, "PK", {derive: "ABS(HASH({source}))"}]
      - [{fk_column}, integer, false, "FK", {derive: "...", fk: other.table.column}]
      # Attributes
      - [{column}, string, false, "Description", {from: source_col}]
      - [{column}, string, true, "Description", {derive: "'constant'"}]

    measures:
      - [count, count_distinct, {pk_column}, "Count", {format: "#,##0"}]

  fact_{name}:
    type: fact
    from: bronze.{provider}.{table}
    primary_key: [{pk_column}]
    partition_by: [date_id]

    schema:
      # Keys
      - [{pk_column}, integer, false, "PK", {derive: "ABS(HASH(CONCAT(...)))"}]
      - [{dim_fk}, integer, false, "FK", {derive: "...", fk: dim_{name}.{pk}}]
      - [date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST({date_col} AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
      # Measures
      - [{measure}, double, false, "Description", {from: source_col}]

    measures:
      - [total, sum, {measure}, "Total", {format: "$#,##0.00"}]
      - [average, avg, {measure}, "Average", {format: "$#,##0.00"}]

# Views (optional)
views:
  vw_{name}:
    description: "View description"
    from: fact_{name}
    joins:
      - {table: dim_{name}, on: "{fk}", type: inner}
    columns:
      - {pk_column}
      - {column: dim_{name}.{col}, as: alias}

# Graph - relationship map
graph:
  nodes:
    dim_{name}: {pk: {pk_column}}
    fact_{name}: {pk: {pk_column}}

  edges:
    fact_to_dim: {from: fact_{name}, to: dim_{name}, fk: {fk_column}}
    fact_to_calendar: {from: fact_{name}, to: temporal.dim_calendar, fk: date_id}

  paths:
    {path_name}:
      description: "Path description"
      via: [table_a, table_b, table_c]

# Metadata (optional)
metadata:
  domain: {domain}
  owner: {team}
  sla_hours: 24
status: active
---

## {Model Name} Model

Documentation for this model.
```

---

### F.3 Table Templates

#### Dimension Table

```yaml
dim_{name}:
  type: dimension
  from: bronze.{provider}.{table}
  filters:
    - "{condition}"
  primary_key: [{pk_column}]
  unique_key: [{natural_key}]

  schema:
    # Primary key - integer surrogate
    - [{pk}_id, integer, false, "PK - surrogate", {derive: "ABS(HASH({source}))"}]

    # Natural key
    - [{natural_key}, string, false, "Natural key", {from: {source}, unique: true}]

    # Foreign keys to other dimensions
    - [{fk}_id, integer, true, "FK to {other}", {derive: "...", fk: {model}.{table}.{column}}]

    # Attributes - from source
    - [{attr}, string, true, "Description", {from: source_column}]

    # Attributes - derived/computed
    - [{attr}, string, true, "Description", {derive: "expression"}]

    # Attributes - with defaults
    - [{attr}, boolean, true, "Description", {default: true}]

  measures:
    - [{name}_count, count_distinct, {pk}_id, "Count of {name}", {format: "#,##0"}]
```

#### Fact Table

```yaml
fact_{name}:
  type: fact
  from: bronze.{provider}.{table}
  filters:
    - "{condition}"
  primary_key: [{pk}_id]
  partition_by: [date_id]

  schema:
    # Primary key - composite surrogate
    - [{pk}_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT({key1}, '_', {key2})))"}]

    # Foreign keys - ALWAYS integers
    - [{dim}_id, integer, false, "FK to {dim}", {derive: "ABS(HASH({source}))", fk: dim_{name}.{pk}_id}]
    - [date_id, integer, false, "FK to calendar", {derive: "CAST(REGEXP_REPLACE(CAST({date_col} AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]

    # Measures - from source
    - [{measure}, double, false, "Description", {from: source_column}]
    - [{measure}, long, true, "Description", {from: source_column}]

    # Measures - computed post-build
    - [{measure}, double, true, "Description", {computed: true}]

  measures:
    - [total_{measure}, sum, {measure}, "Total", {format: "$#,##0.00"}]
    - [avg_{measure}, avg, {measure}, "Average", {format: "$#,##0.00"}]
    - [max_{measure}, max, {measure}, "Maximum", {format: "$#,##0.00"}]
    - [min_{measure}, min, {measure}, "Minimum", {format: "$#,##0.00"}]
    - [{ratio}, expression, "SUM(a) / NULLIF(SUM(b), 0) * 100", "Ratio %", {format: "#,##0.00%"}]
```

#### Computed Fact Table (Post-Build)

```yaml
fact_{name}_computed:
  type: fact
  from: computed  # Special marker - built from other tables
  description: "Computed from {source tables}"
  primary_key: [{pk}_id]
  partition_by: [date_id]

  schema:
    - [{pk}_id, integer, false, "PK", {derive: "..."}]
    - [{dim}_id, integer, false, "FK", {from: {source}_id, fk: dim_{name}.{pk}_id}]
    - [date_id, integer, false, "FK", {from: date_id, fk: temporal.dim_calendar.date_id}]
    # All measures marked as computed
    - [{measure_1}, double, true, "Description", {computed: true}]
    - [{measure_2}, double, true, "Description", {computed: true}]
```

---

### F.4 Schema Column Options

```yaml
schema:
  # Basic column: [name, type, nullable, description]
  - [column_name, string, true, "Description"]

  # With source mapping
  - [column_name, string, true, "Description", {from: source_column}]

  # With derivation (computed at build time)
  - [column_name, integer, false, "Description", {derive: "ABS(HASH(source))"}]

  # With foreign key reference
  - [column_name, integer, false, "FK", {fk: model.table.column}]

  # With derivation AND foreign key
  - [column_name, integer, false, "FK", {derive: "ABS(HASH(x))", fk: model.table.column}]

  # With unique constraint
  - [column_name, string, false, "Natural key", {unique: true}]

  # With default value
  - [column_name, boolean, true, "Flag", {default: true}]
  - [column_name, string, true, "Status", {default: "active"}]

  # With enum constraint
  - [column_name, string, true, "Type", {enum: [TypeA, TypeB, TypeC]}]

  # Post-build computed (filled by separate script)
  - [column_name, double, true, "Computed metric", {computed: true}]

  # With range constraint
  - [column_name, double, true, "Percentage", {range: [0, 100]}]

  # With format hint (for display)
  - [column_name, double, true, "Amount", {format: "$#,##0.00"}]

  # Combined options
  - [column_name, integer, false, "FK with derivation", {derive: "ABS(HASH(x))", fk: table.col, unique: true}]
```

#### Data Types Reference

| Type | Description | Example |
|------|-------------|---------|
| `integer` | 32-bit integer | IDs, counts |
| `long` | 64-bit integer | Large counts, volume |
| `double` | 64-bit float | Prices, percentages |
| `string` | Variable text | Names, codes |
| `boolean` | True/false | Flags |
| `date` | Date only | Trade date |
| `timestamp` | Date + time | Event timestamp |

---

### F.5 Measures Templates

```yaml
measures:
  # Count distinct
  - [{name}_count, count_distinct, {column}, "Count of unique {name}", {format: "#,##0"}]

  # Sum
  - [total_{name}, sum, {column}, "Total {name}", {format: "$#,##0.00"}]

  # Average
  - [avg_{name}, avg, {column}, "Average {name}", {format: "$#,##0.00"}]

  # Min/Max
  - [min_{name}, min, {column}, "Minimum {name}", {format: "$#,##0.00"}]
  - [max_{name}, max, {column}, "Maximum {name}", {format: "$#,##0.00"}]

  # Expression - ratio
  - [{name}_ratio, expression, "SUM(numerator) / NULLIF(SUM(denominator), 0)", "Ratio", {format: "#,##0.00"}]

  # Expression - percentage
  - [{name}_pct, expression, "SUM(part) / NULLIF(SUM(total), 0) * 100", "Percentage", {format: "#,##0.00%"}]

  # Expression - margin
  - [gross_margin, expression, "AVG((revenue - cost) / NULLIF(revenue, 0) * 100)", "Gross Margin %", {format: "#,##0.00%"}]

  # With filter
  - [active_count, count_distinct, id, "Active count", {format: "#,##0", filter: "is_active = true"}]

  # With group by hint
  - [by_category, count_distinct, id, "Count by category", {format: "#,##0", group_by: category}]
```

#### Measure Aggregation Types

| Type | Description | Usage |
|------|-------------|-------|
| `count` | Count rows | `[name, count, column, ...]` |
| `count_distinct` | Count unique | `[name, count_distinct, column, ...]` |
| `sum` | Sum values | `[name, sum, column, ...]` |
| `avg` | Average | `[name, avg, column, ...]` |
| `min` | Minimum | `[name, min, column, ...]` |
| `max` | Maximum | `[name, max, column, ...]` |
| `expression` | Custom SQL | `[name, expression, "SQL", ...]` |

---

### F.6 Graph Templates

```yaml
graph:
  # Nodes - table index with primary keys
  nodes:
    # Dimension
    dim_{name}: {pk: {pk}_id}

    # Fact
    fact_{name}: {pk: {pk}_id}

    # View (virtual node)
    vw_{name}: {pk: {pk}_id, type: view}

    # Composite primary key
    fact_{name}: {pk: [{key1}, {key2}]}

  # Edges - FK relationship index
  edges:
    # Same-model edge (fact to dimension)
    {fact}_to_{dim}: {from: fact_{name}, to: dim_{name}, fk: {fk}_id}

    # Cross-model edge (to another model's table)
    {table}_to_calendar: {from: fact_{name}, to: temporal.dim_calendar, fk: date_id}
    {table}_to_{other}: {from: dim_{name}, to: {model}.{table}, fk: {fk}_id}

    # Optional edge (LEFT JOIN)
    {table}_to_{other}: {from: dim_{name}, to: {model}.{table}, fk: {fk}_id, optional: true}

  # Paths - named multi-hop traversals
  paths:
    # Simple path through own model
    {path_name}:
      description: "Description of what this path represents"
      via: [fact_{name}, dim_{name}]

    # Cross-model path
    {path_name}:
      description: "Path across multiple models"
      via: [fact_{name}, dim_{name}, {other_model}.{table}, {another}.{table}]

    # Empty paths (when not needed)
    # paths: {}
```

---

### F.7 Views Templates

```yaml
views:
  # Filter view - subset of rows
  vw_{name}_filtered:
    description: "Filtered subset description"
    from: {base_table}
    filters:
      - "{column} = '{value}'"
      - "{date_column} >= {value}"
    columns:
      - {col1}
      - {col2}
      - {col3}

  # Join view - denormalized
  vw_{name}_full:
    description: "Denormalized with related dimensions"
    from: fact_{name}
    joins:
      - {table: dim_{name}, on: "{fk}_id", type: inner}
      - {table: temporal.dim_calendar, on: "date_id", type: inner, alias: cal}
      - {table: {model}.{table}, on: "{fk}_id", type: left, alias: x}
    columns:
      # From fact
      - {pk}_id
      - {measure}
      # From dimension (aliased)
      - {column: dim_{name}.{col}, as: {alias}}
      # From calendar
      - {column: cal.date, as: {date_alias}}
      - {column: cal.year, as: year}
      - {column: cal.month_name, as: month}

  # Aggregate view - grouped summary
  vw_{name}_summary:
    description: "Aggregated summary"
    from: fact_{name}
    joins:
      - {table: dim_{name}, on: "{fk}_id", type: inner, alias: d}
      - {table: temporal.dim_calendar, on: "date_id", type: inner, alias: cal}
    filters:
      - "{status} = 'completed'"
    group_by:
      - cal.year
      - cal.month
      - d.{category}
    columns:
      - {column: cal.year, as: year}
      - {column: cal.month, as: month}
      - {column: d.{category}, as: category}
      - {column: "COUNT(DISTINCT {pk}_id)", as: record_count}
      - {column: "SUM({measure})", as: total}
      - {column: "AVG({measure})", as: average}

  # Calculated view - derived metrics
  vw_{name}_metrics:
    description: "Calculated metrics per dimension"
    from: dim_{name}
    joins:
      - {table: fact_{name}, on: "{fk}_id", type: left, alias: f}
    group_by:
      - dim_{name}.{pk}_id
      - dim_{name}.{name}
    columns:
      - {column: dim_{name}.{pk}_id, as: id}
      - {column: dim_{name}.{name}, as: name}
      - {column: "COUNT(f.{pk}_id)", as: transaction_count}
      - {column: "COALESCE(SUM(f.{measure}), 0)", as: total_value}
      - {column: "COALESCE(AVG(f.{measure}), 0)", as: avg_value}
```

---

### F.8 Storage Templates

```yaml
storage:
  format: delta  # delta or parquet

  # Bronze layer - raw ingested data
  bronze:
    provider: {provider_name}  # alpha_vantage, bls, chicago, seed
    tables:
      {logical_name}: {provider}/{table_path}
      # Examples:
      listing_status: alpha_vantage/listing_status
      time_series_daily: alpha_vantage/time_series_daily_adjusted
      unemployment: bls/unemployment
      crimes: chicago/crimes

  # Silver layer - dimensional model output
  silver:
    root: storage/silver/{model_name}

  # Optional: auto vacuum for Delta tables
  auto_vacuum: true  # Enable Delta VACUUM (removes old versions)
```

---

### F.9 Build Configuration Template

```yaml
build:
  # Partitioning strategy
  partitions: [date_id]  # Or [year, month] or []

  # Sort order for efficient queries
  sort_by: [{pk}_id]  # Or [date_id, {pk}_id]

  # Optimize after build
  optimize: true

  # Z-order columns (Delta Lake)
  z_order_by: [{frequently_filtered_col}]

  # Retention for time travel (Delta Lake)
  retention_hours: 168  # 7 days
```

---

### F.10 Metadata Template

```yaml
metadata:
  domain: {domain_name}
  owner: {team_name}
  sla_hours: 24
  tags: [tag1, tag2]
  documentation_url: "https://..."

status: active  # active, deprecated, draft
```

---

### F.11 Common Derivation Patterns

```yaml
# Integer surrogate from single column
{derive: "ABS(HASH({column}))"}

# Integer surrogate from multiple columns
{derive: "ABS(HASH(CONCAT({col1}, '_', {col2})))"}

# Integer surrogate with prefix (for namespacing)
{derive: "ABS(HASH(CONCAT('PREFIX_', {column})))"}

# date_id from DATE column (YYYYMMDD integer)
{derive: "CAST(DATE_FORMAT({date_col}, 'yyyyMMdd') AS INT)"}

# date_id from STRING date (YYYY-MM-DD format)
{derive: "CAST(REGEXP_REPLACE(CAST({date_col} AS STRING), '-', '') AS INT)"}

# date_id from TIMESTAMP
{derive: "CAST(DATE_FORMAT(CAST({ts_col} AS DATE), 'yyyyMMdd') AS INT)"}

# Constant value
{derive: "'constant_string'"}
{derive: "true"}
{derive: "0"}

# Conditional derivation
{derive: "CASE WHEN {col} IS NULL THEN 'Unknown' ELSE {col} END"}
{derive: "COALESCE({col}, 'default')"}

# Type conversion
{derive: "CAST({col} AS STRING)"}
{derive: "CAST({col} AS DOUBLE)"}

# String manipulation
{derive: "UPPER({col})"}
{derive: "TRIM({col})"}
{derive: "CONCAT({col1}, ' ', {col2})"}

# Null check derivation
{derive: "{col} IS NOT NULL"}
```

---

### F.12 Quick Copy Templates

#### Minimal Dimension

```yaml
dim_{name}:
  type: dimension
  from: bronze.{provider}.{table}
  primary_key: [{name}_id]
  schema:
    - [{name}_id, integer, false, "PK", {derive: "ABS(HASH({source}))"}]
    - [{name}_code, string, false, "Code", {from: code, unique: true}]
    - [{name}_name, string, true, "Name", {from: name}]
  measures:
    - [count, count_distinct, {name}_id, "Count", {format: "#,##0"}]
```

#### Minimal Fact

```yaml
fact_{name}:
  type: fact
  from: bronze.{provider}.{table}
  primary_key: [{name}_id]
  partition_by: [date_id]
  schema:
    - [{name}_id, integer, false, "PK", {derive: "ABS(HASH(CONCAT({key1}, '_', {key2})))"}]
    - [{dim}_id, integer, false, "FK", {derive: "ABS(HASH({source}))", fk: dim_{dim}.{dim}_id}]
    - [date_id, integer, false, "FK", {derive: "CAST(REGEXP_REPLACE(CAST({date} AS STRING), '-', '') AS INT)", fk: temporal.dim_calendar.date_id}]
    - [amount, double, false, "Amount", {from: amount}]
  measures:
    - [total, sum, amount, "Total", {format: "$#,##0.00"}]
```

#### Minimal Graph

```yaml
graph:
  nodes:
    dim_{name}: {pk: {name}_id}
    fact_{name}: {pk: {name}_id}
  edges:
    fact_to_dim: {from: fact_{name}, to: dim_{name}, fk: {dim}_id}
    fact_to_calendar: {from: fact_{name}, to: temporal.dim_calendar, fk: date_id}
  paths: {}
```

#### Minimal View

```yaml
views:
  vw_{name}:
    description: "Description"
    from: fact_{name}
    joins:
      - {table: dim_{name}, on: "{dim}_id", type: inner}
    columns:
      - {name}_id
      - amount
      - {column: dim_{name}.{name}_name, as: name}
```

---

## Appendix G: Unified Accounting & Ledger System

This appendix shows how entity templates compose to create a complete double-entry accounting system that works for **both corporate entities AND municipalities**.

### The Problem

Both corporations and municipalities need:
- Chart of Accounts (same structure)
- General Ledger / Journal Entries (same double-entry rules)
- Fiscal Periods (same reporting needs)
- Financial Statements (same accounting principles)

The difference is the **entity that owns the books** - a company vs a municipality.

### Solution: Shared Accounting Templates + Entity-Specific Owners

```
                    _base.entities.entity
                            │
            ┌───────────────┴───────────────┐
            │                               │
   _base.entities.organization    _base.accounting.ledger_entity
            │                               │
    ┌───────┴───────┐               ┌───────┴───────┐
    │               │               │               │
corporate.      municipal.     _base.accounting.  _base.accounting.
dim_company    dim_municipality  journal_entry    chart_of_accounts
    │               │               │               │
    └───────┬───────┘               └───────┬───────┘
            │                               │
            └───────────┬───────────────────┘
                        │
                ┌───────┴───────┐
                │               │
        corporate.ledger   municipal.ledger
        (fact_journal_     (fact_journal_
         entries)           entries)
```

---

### G.1 Base Accounting Entity Template

The ledger entity is the "owner" of a set of books - can be a company, municipality, fund, department, etc.

```yaml
# domains/_base/accounting/ledger_entity.md
---
type: domain-base
base_name: ledger_entity
description: "Base template for any entity that maintains accounting books"

extends: _base.entities.entity

tables:
  _dim_ledger_entity:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [ledger_entity_id]

    schema:
      # === IDENTITY ===
      - [ledger_entity_id, integer, false, "PK - surrogate"]
      - [ledger_entity_code, string, false, "Business code", {unique: true}]
      - [ledger_entity_name, string, false, "Legal/official name"]

      # === CLASSIFICATION ===
      - [entity_type, string, false, "Company, Municipality, Fund, Department, etc."]
      - [legal_structure, string, true, "Corporation, Government, Nonprofit, etc."]

      # === FISCAL CONFIGURATION ===
      - [fiscal_year_start_month, integer, true, "1-12 (1=Jan)", {default: 1}]
      - [fiscal_year_end_month, integer, true, "1-12 (12=Dec)", {default: 12}]
      - [reporting_currency, string, true, "Primary currency", {default: "USD"}]
      - [accounting_standard, string, true, "GAAP, IFRS, GASB, etc."]

      # === REGULATORY ===
      - [tax_id, string, true, "Tax ID / EIN"]
      - [regulatory_id, string, true, "SEC CIK, DUNS, CAGE, etc."]
      - [jurisdiction, string, true, "State/country of incorporation"]

      # === HIERARCHY (for consolidation) ===
      - [parent_entity_id, integer, true, "FK to parent (for consolidation)"]
      - [consolidation_type, string, true, "Full, Proportional, Equity, None"]
      - [elimination_entity, boolean, true, "Used for intercompany eliminations", {default: false}]

      # Inherits: audit, status, versioning from entity

    measures:
      - [entity_count, count_distinct, ledger_entity_id, "Number of entities", {format: "#,##0"}]

status: active
---

## Ledger Entity Base Template

Any entity that maintains a general ledger extends this template.

### Key Concept

The "ledger entity" is the **owner of the books**. It could be:
- A corporation (corporate.dim_company)
- A municipality (municipal.dim_municipality)
- A fund within a municipality (municipal.dim_fund)
- A department or cost center
- A joint venture

All of these share the same accounting structure but have different attributes.
```

---

### G.2 Base Journal Entry Template

The core of double-entry bookkeeping - every entry has debits and credits that must balance.

```yaml
# domains/_base/accounting/journal_entry.md
---
type: domain-base
base_name: journal_entry
description: "Base template for double-entry journal entries"

extends: _base.entities.entity

depends_on: [temporal]

tables:
  # Journal Entry Header
  _fact_journal_entry:
    type: fact
    extends: _base.entities.entity._fact_entity_event
    primary_key: [journal_entry_id]
    partition_by: [posting_date_id]

    schema:
      # === IDENTITY ===
      - [journal_entry_id, integer, false, "PK - surrogate"]
      - [journal_number, string, false, "Business journal number", {unique: true}]
      - [entry_description, string, true, "Journal entry description"]

      # === ENTITY OWNERSHIP (FK mapped by child) ===
      - [ledger_entity_id, integer, false, "FK to ledger entity owner"]

      # === TEMPORAL ===
      - [transaction_date_id, integer, false, "FK - when transaction occurred", {fk: temporal.dim_calendar.date_id}]
      - [posting_date_id, integer, false, "FK - when posted to ledger", {fk: temporal.dim_calendar.date_id}]
      - [fiscal_period_id, integer, false, "FK - fiscal period"]
      - [posting_timestamp, timestamp, true, "Exact posting time"]

      # === CLASSIFICATION ===
      - [journal_type, string, false, "Standard, Adjusting, Closing, Reversing, etc."]
      - [entry_status, string, false, "Draft, Pending, Posted, Reversed", {default: "Draft"}]
      - [auto_reverse, boolean, true, "Auto-reverse next period", {default: false}]
      - [reversal_of_id, integer, true, "FK to reversed entry"]

      # === TOTALS (computed/validated) ===
      - [total_debits, double, false, "Sum of all debit lines"]
      - [total_credits, double, false, "Sum of all credit lines"]
      - [is_balanced, boolean, false, "Debits = Credits", {derive: "total_debits = total_credits"}]

      # === APPROVAL ===
      - [prepared_by, string, true, "User who prepared"]
      - [approved_by, string, true, "User who approved"]
      - [approved_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]

      # Inherits: source_system, source_id, created_timestamp from entity

    measures:
      - [entry_count, count_distinct, journal_entry_id, "Number of entries", {format: "#,##0"}]
      - [total_debits_sum, sum, total_debits, "Total debits", {format: "$#,##0.00"}]
      - [unbalanced_count, count_distinct, journal_entry_id, "Unbalanced entries", {format: "#,##0", filter: "is_balanced = false"}]

  # Journal Entry Lines (the actual debits and credits)
  _fact_journal_line:
    type: fact
    primary_key: [journal_line_id]
    partition_by: [posting_date_id]

    schema:
      # === IDENTITY ===
      - [journal_line_id, integer, false, "PK - surrogate"]
      - [journal_entry_id, integer, false, "FK to header", {fk: _fact_journal_entry.journal_entry_id}]
      - [line_number, integer, false, "Line sequence within entry"]

      # === ACCOUNT ===
      - [account_id, integer, false, "FK to chart of accounts"]
      - [account_code, string, false, "Account code (denormalized)"]

      # === AMOUNT (one of debit/credit is zero) ===
      - [debit_amount, double, false, "Debit amount (0 if credit)", {default: 0}]
      - [credit_amount, double, false, "Credit amount (0 if debit)", {default: 0}]
      - [amount, double, false, "Signed amount (debit=+, credit=-)", {derive: "debit_amount - credit_amount"}]
      - [functional_amount, double, true, "Amount in functional currency"]
      - [reporting_amount, double, true, "Amount in reporting currency"]

      # === DIMENSIONS (for analysis - mapped by child) ===
      - [cost_center_id, integer, true, "FK to cost center"]
      - [department_id, integer, true, "FK to department"]
      - [project_id, integer, true, "FK to project"]
      - [location_id, integer, true, "FK to location"]

      # === DESCRIPTION ===
      - [line_description, string, true, "Line memo"]
      - [reference, string, true, "External reference"]

      # === TEMPORAL (denormalized from header) ===
      - [posting_date_id, integer, false, "FK to calendar (from header)", {fk: temporal.dim_calendar.date_id}]

    measures:
      - [line_count, count_distinct, journal_line_id, "Number of lines", {format: "#,##0"}]
      - [sum_debits, sum, debit_amount, "Total debits", {format: "$#,##0.00"}]
      - [sum_credits, sum, credit_amount, "Total credits", {format: "$#,##0.00"}]
      - [net_amount, sum, amount, "Net amount", {format: "$#,##0.00"}]

status: active
---

## Journal Entry Base Template

Double-entry bookkeeping with header and line structure.

### Double-Entry Rules

Every journal entry MUST:
1. Have at least 2 lines
2. Total debits = Total credits (balanced)
3. Each line affects exactly one account

### Entry Types

| Type | Purpose | Example |
|------|---------|---------|
| Standard | Normal business transactions | Invoice, payment |
| Adjusting | Period-end adjustments | Accruals, deferrals |
| Closing | Close temporary accounts | Revenue/expense to retained earnings |
| Reversing | Auto-reverse accruals | Reverse accrued expenses |

### Debit/Credit Convention

| Account Type | Debit | Credit |
|--------------|-------|--------|
| Asset | Increase | Decrease |
| Liability | Decrease | Increase |
| Equity | Decrease | Increase |
| Revenue | Decrease | Increase |
| Expense | Increase | Decrease |
```

---

### G.3 Base Chart of Accounts Template

Shared account structure for all ledger entities.

```yaml
# domains/_base/accounting/chart_of_accounts.md
---
type: domain-base
base_name: chart_of_accounts
description: "Base template for chart of accounts hierarchy"

extends: _base.entities.entity

tables:
  # Account Category (top level)
  _dim_account_category:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [category_id]

    schema:
      - [category_id, integer, false, "PK"]
      - [category_code, string, false, "A, L, E, R, X", {unique: true}]
      - [category_name, string, false, "Assets, Liabilities, etc."]
      - [normal_balance, string, false, "Debit or Credit"]
      - [display_order, integer, false, "Sort order"]
      - [financial_statement, string, false, "Balance Sheet, Income Statement"]

  # Account Type (sub-level)
  _dim_account_type:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [account_type_id]

    schema:
      - [account_type_id, integer, false, "PK"]
      - [category_id, integer, false, "FK to category", {fk: _dim_account_category.category_id}]
      - [type_code, string, false, "Type code", {unique: true}]
      - [type_name, string, false, "Current Assets, Fixed Assets, etc."]
      - [display_order, integer, false, "Sort order"]

  # Account (leaf level - the actual GL accounts)
  _dim_account:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [account_id]

    schema:
      # === IDENTITY ===
      - [account_id, integer, false, "PK"]
      - [account_code, string, false, "Account number", {unique: true}]
      - [account_name, string, false, "Account name"]
      - [account_description, string, true, "Description"]

      # === HIERARCHY ===
      - [account_type_id, integer, false, "FK to type", {fk: _dim_account_type.account_type_id}]
      - [parent_account_id, integer, true, "FK to parent (for sub-accounts)"]
      - [hierarchy_level, integer, true, "Depth in account tree"]
      - [hierarchy_path, string, true, "Full path"]

      # === CLASSIFICATION ===
      - [normal_balance, string, false, "Debit or Credit"]
      - [account_class, string, true, "Control, Detail, Statistical"]
      - [is_posting_account, boolean, false, "Can post to this account", {default: true}]
      - [is_control_account, boolean, false, "Control account (AR, AP)", {default: false}]

      # === REPORTING MAPPINGS ===
      - [gaap_mapping, string, true, "US GAAP line item"]
      - [ifrs_mapping, string, true, "IFRS line item"]
      - [gasb_mapping, string, true, "GASB line item (government)"]
      - [tax_mapping, string, true, "Tax form line item"]

      # === BUDGET ===
      - [is_budgeted, boolean, true, "Subject to budget control", {default: true}]
      - [budget_category, string, true, "Budget category"]

      # Inherits: audit, status, versioning from entity

    measures:
      - [account_count, count_distinct, account_id, "Number of accounts", {format: "#,##0"}]
      - [posting_account_count, count_distinct, account_id, "Posting accounts", {format: "#,##0", filter: "is_posting_account = true"}]

status: active
---

## Chart of Accounts Base Template

Hierarchical account structure with regulatory mappings.

### Account Hierarchy

```
Category (5)
├── Assets (A) - Normal: Debit
│   ├── Current Assets (A-CA)
│   │   ├── 1000 Cash
│   │   ├── 1100 Accounts Receivable (Control)
│   │   └── 1200 Inventory
│   └── Fixed Assets (A-FA)
│       ├── 1500 Property & Equipment
│       └── 1600 Accumulated Depreciation
├── Liabilities (L) - Normal: Credit
│   ├── Current Liabilities (L-CL)
│   └── Long-term Liabilities (L-LT)
├── Equity (E) - Normal: Credit
├── Revenue (R) - Normal: Credit
└── Expenses (X) - Normal: Debit
```

### Regulatory Mappings

The same account structure can map to different reporting standards:

| Account | GAAP | GASB (Government) |
|---------|------|-------------------|
| 1000 Cash | Cash and equivalents | Cash and pooled investments |
| 4000 Revenue | Revenue from contracts | Program revenues |
| 6100 Salaries | Compensation expense | Personal services |
```

---

### G.4 Fiscal Period Template

Shared fiscal period dimension for all entities.

```yaml
# domains/_base/accounting/fiscal_period.md
---
type: domain-base
base_name: fiscal_period
description: "Base template for fiscal period dimension"

extends: _base.entities.entity

depends_on: [temporal]

tables:
  _dim_fiscal_period:
    type: dimension
    extends: _base.entities.entity._dim_entity
    primary_key: [fiscal_period_id]

    schema:
      # === IDENTITY ===
      - [fiscal_period_id, integer, false, "PK"]
      - [ledger_entity_id, integer, false, "FK to ledger entity"]
      - [fiscal_year, integer, false, "Fiscal year"]
      - [fiscal_period, integer, false, "Period within year (1-13)"]
      - [period_name, string, false, "Period name (Jan, Feb, Adj)"]

      # === DATES ===
      - [period_start_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [period_end_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]

      # === STATUS ===
      - [period_status, string, false, "Open, Closed, Locked", {default: "Open"}]
      - [closed_date_id, integer, true, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [closed_by, string, true, "User who closed"]

      # === CLASSIFICATION ===
      - [is_adjustment_period, boolean, false, "Adjustment period (period 13)", {default: false}]
      - [is_year_end, boolean, false, "Last period of fiscal year", {default: false}]
      - [quarter, integer, true, "Fiscal quarter (1-4)"]

    measures:
      - [period_count, count_distinct, fiscal_period_id, "Number of periods", {format: "#,##0"}]
      - [open_periods, count_distinct, fiscal_period_id, "Open periods", {format: "#,##0", filter: "period_status = 'Open'"}]

status: active
---
```

---

### G.5 Corporate Implementation

How a corporation uses the accounting templates.

```yaml
# domains/corporate/ledger.md
---
type: domain-model
model: corporate_ledger
version: 1.0
description: "Corporate general ledger - journal entries and account balances"

# Inherit accounting templates
extends: _base.accounting.journal_entry

depends_on: [temporal, corporate_company, corporate_chart_of_accounts]

storage:
  format: delta
  bronze:
    provider: erp
    tables:
      journal_entries: erp/gl_journal_entries
      journal_lines: erp/gl_journal_lines
  silver:
    root: storage/silver/corporate_ledger

tables:
  # Company dimension (ledger entity owner)
  dim_company:
    type: dimension
    extends: _base.accounting.ledger_entity._dim_ledger_entity
    from: bronze.erp.companies
    primary_key: [company_id]

    schema:
      # Override ledger_entity_id with company_id
      - [company_id, integer, false, "PK", {derive: "ABS(HASH(company_code))"}]
      - [ledger_entity_id, integer, false, "Alias for company_id", {derive: "company_id"}]

      # Company-specific fields
      - [cik, string, true, "SEC Central Index Key"]
      - [ticker, string, true, "Stock ticker"]
      - [sic_code, string, true, "SIC industry code"]
      - [naics_code, string, true, "NAICS industry code"]
      - [sector, string, true, "Business sector"]
      - [industry, string, true, "Industry"]

      # Inherits: fiscal config, regulatory, hierarchy from ledger_entity

  # Journal entries owned by company
  fact_journal_entries:
    type: fact
    extends: _base.accounting.journal_entry._fact_journal_entry
    from: bronze.erp.journal_entries
    primary_key: [journal_entry_id]
    partition_by: [posting_date_id]

    schema:
      # Map ledger_entity_id to company_id
      - [ledger_entity_id, integer, false, "FK to company", {derive: "ABS(HASH(company_code))", fk: dim_company.company_id}]

      # Inherits all journal entry fields

  # Journal lines
  fact_journal_lines:
    type: fact
    extends: _base.accounting.journal_entry._fact_journal_line
    from: bronze.erp.journal_lines
    primary_key: [journal_line_id]
    partition_by: [posting_date_id]

    schema:
      # Map account_id to corporate chart of accounts
      - [account_id, integer, false, "FK to account", {derive: "ABS(HASH(account_code))", fk: corporate_chart_of_accounts.dim_account.account_id}]

      # Inherits all journal line fields

graph:
  nodes:
    dim_company: {pk: company_id}
    fact_journal_entries: {pk: journal_entry_id}
    fact_journal_lines: {pk: journal_line_id}

  edges:
    entries_to_company: {from: fact_journal_entries, to: dim_company, fk: ledger_entity_id}
    entries_to_calendar: {from: fact_journal_entries, to: temporal.dim_calendar, fk: posting_date_id}
    lines_to_entry: {from: fact_journal_lines, to: fact_journal_entries, fk: journal_entry_id}
    lines_to_account: {from: fact_journal_lines, to: corporate_chart_of_accounts.dim_account, fk: account_id}

  paths:
    company_to_accounts:
      description: "Company journal entries to account details"
      via: [dim_company, fact_journal_entries, fact_journal_lines, corporate_chart_of_accounts.dim_account]

status: active
---
```

---

### G.6 Municipal Implementation

How a municipality uses the **same** accounting templates.

```yaml
# domains/municipal/ledger.md
---
type: domain-model
model: municipal_ledger
version: 1.0
description: "Municipal general ledger - fund accounting with GASB compliance"

# Inherit the SAME accounting templates
extends: _base.accounting.journal_entry

depends_on: [temporal, municipal_entity, municipal_chart_of_accounts, municipal_funds]

storage:
  format: delta
  bronze:
    provider: munis  # Municipal ERP system
    tables:
      journal_entries: munis/gl_journal_entries
      journal_lines: munis/gl_journal_lines
  silver:
    root: storage/silver/municipal_ledger

tables:
  # Municipality dimension (ledger entity owner)
  dim_municipality:
    type: dimension
    extends: _base.accounting.ledger_entity._dim_ledger_entity
    from: bronze.munis.municipalities
    primary_key: [municipality_id]

    schema:
      # Override ledger_entity_id with municipality_id
      - [municipality_id, integer, false, "PK", {derive: "ABS(HASH(municipality_code))"}]
      - [ledger_entity_id, integer, false, "Alias", {derive: "municipality_id"}]

      # Municipality-specific fields
      - [municipality_type, string, false, "City, County, Township, District"]
      - [state_code, string, false, "State abbreviation"]
      - [fips_code, string, true, "Federal FIPS code"]
      - [census_id, string, true, "Census Bureau ID"]
      - [population, long, true, "Population"]
      - [square_miles, double, true, "Area in square miles"]

      # Government-specific regulatory
      - [duns_number, string, true, "D-U-N-S Number"]
      - [cage_code, string, true, "CAGE Code (federal contracts)"]
      - [sam_uei, string, true, "SAM Unique Entity ID"]

      # Inherits: fiscal config, hierarchy from ledger_entity

  # Fund dimension (unique to government accounting)
  dim_fund:
    type: dimension
    extends: _base.accounting.ledger_entity._dim_ledger_entity
    from: bronze.munis.funds
    primary_key: [fund_id]

    schema:
      - [fund_id, integer, false, "PK", {derive: "ABS(HASH(fund_code))"}]
      - [municipality_id, integer, false, "FK to municipality", {fk: dim_municipality.municipality_id}]
      - [fund_code, string, false, "Fund code", {unique: true}]
      - [fund_name, string, false, "Fund name"]

      # GASB Fund Classification
      - [fund_category, string, false, "Governmental, Proprietary, Fiduciary"]
      - [fund_type, string, false, "General, Special Revenue, Debt Service, etc."]
      - [major_fund, boolean, false, "Major fund for CAFR", {default: false}]

      # Budget
      - [budgetary_basis, string, true, "Cash, Modified Accrual, Full Accrual"]
      - [legally_adopted_budget, boolean, true, "Has legal budget", {default: true}]

  # Journal entries - same structure, different owner
  fact_journal_entries:
    type: fact
    extends: _base.accounting.journal_entry._fact_journal_entry
    from: bronze.munis.journal_entries
    primary_key: [journal_entry_id]
    partition_by: [posting_date_id]

    schema:
      # Map to municipality AND fund (dual ownership in government)
      - [ledger_entity_id, integer, false, "FK to municipality", {derive: "ABS(HASH(municipality_code))", fk: dim_municipality.municipality_id}]
      - [fund_id, integer, false, "FK to fund", {derive: "ABS(HASH(fund_code))", fk: dim_fund.fund_id}]

      # Government-specific fields
      - [appropriation_id, integer, true, "FK to budget appropriation"]
      - [grant_id, integer, true, "FK to grant (if grant-funded)"]
      - [encumbrance_type, string, true, "Pre-encumbrance, Encumbrance, Expenditure"]

  # Journal lines - same structure
  fact_journal_lines:
    type: fact
    extends: _base.accounting.journal_entry._fact_journal_line
    from: bronze.munis.journal_lines
    primary_key: [journal_line_id]
    partition_by: [posting_date_id]

    schema:
      # Map to municipal chart of accounts (GASB-compliant)
      - [account_id, integer, false, "FK to account", {derive: "ABS(HASH(account_code))", fk: municipal_chart_of_accounts.dim_account.account_id}]

      # Government-specific dimensions
      - [program_id, integer, true, "FK to program"]
      - [function_id, integer, true, "FK to function (GASB function)"]
      - [grant_id, integer, true, "FK to grant"]
      - [project_id, integer, true, "FK to capital project"]

graph:
  nodes:
    dim_municipality: {pk: municipality_id}
    dim_fund: {pk: fund_id}
    fact_journal_entries: {pk: journal_entry_id}
    fact_journal_lines: {pk: journal_line_id}

  edges:
    entries_to_municipality: {from: fact_journal_entries, to: dim_municipality, fk: ledger_entity_id}
    entries_to_fund: {from: fact_journal_entries, to: dim_fund, fk: fund_id}
    entries_to_calendar: {from: fact_journal_entries, to: temporal.dim_calendar, fk: posting_date_id}
    lines_to_entry: {from: fact_journal_lines, to: fact_journal_entries, fk: journal_entry_id}
    lines_to_account: {from: fact_journal_lines, to: municipal_chart_of_accounts.dim_account, fk: account_id}
    fund_to_municipality: {from: dim_fund, to: dim_municipality, fk: municipality_id}

  paths:
    municipality_to_accounts:
      description: "Municipality → Fund → Journal → Account"
      via: [dim_municipality, dim_fund, fact_journal_entries, fact_journal_lines, municipal_chart_of_accounts.dim_account]

status: active
---

## Municipal Ledger

Government fund accounting with GASB compliance.

### Key Differences from Corporate

| Aspect | Corporate | Municipal |
|--------|-----------|-----------|
| Owner | Company | Municipality + Fund |
| Standards | GAAP/IFRS | GASB |
| Account mapping | gaap_mapping | gasb_mapping |
| Extra dimensions | Cost center | Fund, Program, Grant |
| Budget control | Optional | Legally required |
| Encumbrances | Rare | Required |
```

---

### G.7 Cross-Domain Queries

Because both use the same base templates, you can query across domains.

```sql
-- Compare account balances across corporate and municipal entities
SELECT
    'Corporate' AS entity_type,
    c.company_name AS entity_name,
    a.account_code,
    a.account_name,
    SUM(jl.debit_amount) AS total_debits,
    SUM(jl.credit_amount) AS total_credits
FROM corporate_ledger.fact_journal_lines jl
JOIN corporate_ledger.fact_journal_entries je ON jl.journal_entry_id = je.journal_entry_id
JOIN corporate_ledger.dim_company c ON je.ledger_entity_id = c.company_id
JOIN corporate_chart_of_accounts.dim_account a ON jl.account_id = a.account_id
WHERE je.posting_date_id BETWEEN 20250101 AND 20251231
GROUP BY c.company_name, a.account_code, a.account_name

UNION ALL

SELECT
    'Municipal' AS entity_type,
    m.municipality_name AS entity_name,
    a.account_code,
    a.account_name,
    SUM(jl.debit_amount) AS total_debits,
    SUM(jl.credit_amount) AS total_credits
FROM municipal_ledger.fact_journal_lines jl
JOIN municipal_ledger.fact_journal_entries je ON jl.journal_entry_id = je.journal_entry_id
JOIN municipal_ledger.dim_municipality m ON je.ledger_entity_id = m.municipality_id
JOIN municipal_chart_of_accounts.dim_account a ON jl.account_id = a.account_id
WHERE je.posting_date_id BETWEEN 20250101 AND 20251231
GROUP BY m.municipality_name, a.account_code, a.account_name;
```

---

### G.8 Summary: Template Composition

```
Entity Templates Used:
├── _base.entities.entity           → Common audit/status/versioning
├── _base.entities.organization     → Company/Municipality base
│
Accounting Templates Used:
├── _base.accounting.ledger_entity  → Books owner (extends entity)
├── _base.accounting.journal_entry  → Double-entry transactions
├── _base.accounting.chart_of_accounts → Account hierarchy
└── _base.accounting.fiscal_period  → Reporting periods
│
Corporate Implementation:
├── corporate.dim_company           → extends ledger_entity + organization
├── corporate.fact_journal_entries  → extends journal_entry
└── corporate.fact_journal_lines    → extends journal_line
│
Municipal Implementation:
├── municipal.dim_municipality      → extends ledger_entity + organization
├── municipal.dim_fund              → extends ledger_entity (GASB-specific)
├── municipal.fact_journal_entries  → extends journal_entry + fund FK
└── municipal.fact_journal_lines    → extends journal_line + program/grant FKs
```

**Key Insight**: The accounting templates are **domain-agnostic**. The same journal entry structure works for:
- Corporations (GAAP/IFRS)
- Municipalities (GASB)
- Nonprofits (FASB ASC 958)
- Healthcare (specialized regulations)

Only the **owner entity** and **dimensional attributes** change - the core accounting logic is shared.

---

## Appendix H: Storage Map

This appendix shows the actual storage layout for the accounting/ledger system - what gets written to disk and where.

### Key Principle: Templates Don't Create Storage

```
domains/_base/           ← YAML definitions only - NO storage created
    ├── entities/
    ├── accounting/
    └── ...

storage/                 ← Actual data lives here
    ├── bronze/          ← Raw ingested data (by provider)
    └── silver/          ← Dimensional models (by domain)
```

**Only `type: domain-model` creates storage. Templates (`type: domain-base`) are schema definitions only.**

---

### H.1 Complete Storage Tree

```
storage/
│
├── bronze/                              # Raw data - organized by PROVIDER
│   │
│   ├── alpha_vantage/                   # Securities data provider
│   │   ├── listing_status/              # Delta table
│   │   │   ├── _delta_log/
│   │   │   └── part-*.parquet
│   │   ├── time_series_daily_adjusted/
│   │   ├── income_statement/
│   │   ├── balance_sheet/
│   │   ├── cash_flow/
│   │   └── dividends/
│   │
│   ├── erp/                             # Corporate ERP system
│   │   ├── companies/
│   │   ├── gl_journal_entries/
│   │   ├── gl_journal_lines/
│   │   ├── chart_of_accounts/
│   │   ├── cost_centers/
│   │   └── fiscal_periods/
│   │
│   ├── munis/                           # Municipal ERP system
│   │   ├── municipalities/
│   │   ├── funds/
│   │   ├── gl_journal_entries/
│   │   ├── gl_journal_lines/
│   │   ├── chart_of_accounts/
│   │   ├── programs/
│   │   ├── grants/
│   │   └── fiscal_periods/
│   │
│   ├── bls/                             # Bureau of Labor Statistics
│   │   └── unemployment/
│   │
│   ├── chicago/                         # Chicago Data Portal
│   │   ├── crimes/
│   │   └── permits/
│   │
│   └── seed/                            # Seeded/generated data
│       ├── calendar/
│       └── coa_standard/
│
│
├── silver/                              # Dimensional models - organized by DOMAIN
│   │
│   ├── temporal/                        # Foundation model
│   │   └── dim_calendar/                # Delta table
│   │       ├── _delta_log/
│   │       └── part-*.parquet
│   │
│   ├── corporate/                       # Corporate domain
│   │   │
│   │   ├── company/                     # company model
│   │   │   └── dim_company/
│   │   │
│   │   ├── chart_of_accounts/           # corporate_chart_of_accounts model
│   │   │   ├── dim_account_category/
│   │   │   ├── dim_account_type/
│   │   │   └── dim_account/
│   │   │
│   │   ├── ledger/                      # corporate_ledger model
│   │   │   ├── fact_journal_entries/
│   │   │   │   ├── _delta_log/
│   │   │   │   ├── posting_date_id=20250101/
│   │   │   │   ├── posting_date_id=20250102/
│   │   │   │   └── ...
│   │   │   └── fact_journal_lines/
│   │   │       ├── _delta_log/
│   │   │       ├── posting_date_id=20250101/
│   │   │       └── ...
│   │   │
│   │   ├── fiscal_periods/              # corporate_fiscal_periods model
│   │   │   └── dim_fiscal_period/
│   │   │
│   │   └── financial_statements/        # corporate_financial_statements model
│   │       ├── fact_income_statement/
│   │       ├── fact_balance_sheet/
│   │       └── fact_cash_flow/
│   │
│   ├── municipal/                       # Municipal domain
│   │   │
│   │   ├── entity/                      # municipal_entity model
│   │   │   └── dim_municipality/
│   │   │
│   │   ├── funds/                       # municipal_funds model
│   │   │   └── dim_fund/
│   │   │
│   │   ├── chart_of_accounts/           # municipal_chart_of_accounts model
│   │   │   ├── dim_account_category/
│   │   │   ├── dim_account_type/
│   │   │   └── dim_account/
│   │   │
│   │   ├── ledger/                      # municipal_ledger model
│   │   │   ├── fact_journal_entries/
│   │   │   │   ├── _delta_log/
│   │   │   │   ├── posting_date_id=20250101/
│   │   │   │   └── ...
│   │   │   └── fact_journal_lines/
│   │   │
│   │   ├── fiscal_periods/
│   │   │   └── dim_fiscal_period/
│   │   │
│   │   ├── programs/
│   │   │   └── dim_program/
│   │   │
│   │   └── grants/
│   │       ├── dim_grant/
│   │       └── fact_grant_expenditures/
│   │
│   ├── securities/                      # Securities domain
│   │   │
│   │   ├── securities/                  # securities (master) model
│   │   │   ├── dim_security/
│   │   │   └── fact_security_prices/
│   │   │       ├── _delta_log/
│   │   │       ├── date_id=20250101/
│   │   │       └── ...
│   │   │
│   │   └── stocks/                      # stocks (child) model
│   │       ├── dim_stock/
│   │       ├── fact_stock_technicals/
│   │       ├── fact_dividends/
│   │       └── fact_splits/
│   │
│   └── chicago/                         # Chicago municipal domain
│       ├── public_safety/
│       │   └── fact_crimes/
│       └── permits/
│           └── fact_permits/
│
│
└── duckdb/                              # DuckDB catalog (queries Silver)
    └── analytics.db
```

---

### H.2 Storage Configuration Mapping

The `storage:` section in each model maps to actual paths:

```yaml
# In domains/corporate/ledger.md
storage:
  format: delta
  bronze:
    provider: erp                        # → storage/bronze/erp/
    tables:
      journal_entries: erp/gl_journal_entries    # → storage/bronze/erp/gl_journal_entries/
      journal_lines: erp/gl_journal_lines        # → storage/bronze/erp/gl_journal_lines/
  silver:
    root: storage/silver/corporate/ledger        # → storage/silver/corporate/ledger/
```

**Resulting paths:**

| Config Reference | Actual Path |
|------------------|-------------|
| `bronze.erp.gl_journal_entries` | `storage/bronze/erp/gl_journal_entries/` |
| `bronze.erp.gl_journal_lines` | `storage/bronze/erp/gl_journal_lines/` |
| `corporate_ledger.fact_journal_entries` | `storage/silver/corporate/ledger/fact_journal_entries/` |
| `corporate_ledger.fact_journal_lines` | `storage/silver/corporate/ledger/fact_journal_lines/` |

---

### H.3 Bronze Layer Detail

Bronze stores raw data exactly as received from source systems.

```
storage/bronze/erp/gl_journal_entries/
├── _delta_log/                          # Delta Lake transaction log
│   ├── 00000000000000000000.json        # Initial commit
│   ├── 00000000000000000001.json        # Subsequent commits
│   └── ...
├── part-00000-*.snappy.parquet          # Data files
├── part-00001-*.snappy.parquet
└── ...
```

**Bronze Schema** (raw from source):
```
gl_journal_entries (Bronze)
├── journal_id          (string)    ← Source system ID
├── company_code        (string)    ← Source company code
├── journal_date        (string)    ← Date as string
├── posting_date        (string)
├── description         (string)
├── total_debit         (decimal)
├── total_credit        (decimal)
├── status              (string)
├── created_by          (string)
├── created_at          (timestamp)
└── _ingestion_ts       (timestamp) ← Added by ingestion
```

---

### H.4 Silver Layer Detail

Silver stores transformed dimensional model with:
- Integer surrogate keys
- Foreign key relationships
- Partitioning for query performance

```
storage/silver/corporate/ledger/fact_journal_entries/
├── _delta_log/
│   ├── 00000000000000000000.json
│   └── ...
├── posting_date_id=20250101/            # Partitioned by posting_date_id
│   ├── part-00000-*.snappy.parquet
│   └── ...
├── posting_date_id=20250102/
│   └── ...
└── posting_date_id=20250103/
    └── ...
```

**Silver Schema** (dimensional model):
```
fact_journal_entries (Silver)
├── journal_entry_id    (integer)   ← PK: ABS(HASH(journal_id))
├── journal_number      (string)    ← Natural key
├── ledger_entity_id    (integer)   ← FK to dim_company
├── transaction_date_id (integer)   ← FK to dim_calendar (YYYYMMDD)
├── posting_date_id     (integer)   ← FK to dim_calendar (partition key)
├── fiscal_period_id    (integer)   ← FK to dim_fiscal_period
├── journal_type        (string)
├── entry_status        (string)
├── total_debits        (double)
├── total_credits       (double)
├── is_balanced         (boolean)
├── created_timestamp   (timestamp)
├── source_system       (string)
└── source_id           (string)
```

---

### H.5 Partitioning Strategy

| Table Type | Partition Key | Rationale |
|------------|---------------|-----------|
| `fact_journal_entries` | `posting_date_id` | Queries filter by posting date |
| `fact_journal_lines` | `posting_date_id` | Co-partitioned with header |
| `fact_security_prices` | `date_id` | Time-series queries |
| `fact_income_statement` | `fiscal_year` | Annual/quarterly analysis |
| `dim_*` | None | Small tables, full scan OK |

**Partition pruning example:**
```sql
-- Only reads partitions 20250101-20250131
SELECT * FROM corporate_ledger.fact_journal_entries
WHERE posting_date_id BETWEEN 20250101 AND 20250131;
```

---

### H.6 Size Estimates

Typical storage sizes for a mid-size organization:

| Layer | Table | Rows | Size | Partitions |
|-------|-------|------|------|------------|
| **Bronze** | | | | |
| | erp/gl_journal_entries | 500K/year | ~100 MB | None |
| | erp/gl_journal_lines | 5M/year | ~1 GB | None |
| | alpha_vantage/time_series_daily | 50M | ~5 GB | None |
| **Silver** | | | | |
| | corporate/ledger/fact_journal_entries | 500K/year | ~80 MB | 365/year |
| | corporate/ledger/fact_journal_lines | 5M/year | ~800 MB | 365/year |
| | securities/securities/fact_security_prices | 50M | ~4 GB | ~5000 dates |
| | temporal/dim_calendar | 18K | ~2 MB | None |

---

### H.7 Storage Configuration File

The `configs/storage.json` file maps logical names to physical paths:

```json
{
  "version": "2.0",
  "storage_root": "/shared/storage",

  "bronze": {
    "path_template": "{storage_root}/bronze/{provider}/{table}",
    "format": "delta",
    "providers": {
      "alpha_vantage": {
        "tables": ["listing_status", "time_series_daily_adjusted", "income_statement", "balance_sheet", "cash_flow", "dividends"]
      },
      "erp": {
        "tables": ["companies", "gl_journal_entries", "gl_journal_lines", "chart_of_accounts", "cost_centers", "fiscal_periods"]
      },
      "munis": {
        "tables": ["municipalities", "funds", "gl_journal_entries", "gl_journal_lines", "chart_of_accounts", "programs", "grants", "fiscal_periods"]
      },
      "seed": {
        "tables": ["calendar", "coa_standard"]
      }
    }
  },

  "silver": {
    "path_template": "{storage_root}/silver/{domain}/{model}/{table}",
    "format": "delta",
    "domains": {
      "temporal": {
        "models": {
          "temporal": ["dim_calendar"]
        }
      },
      "corporate": {
        "models": {
          "company": ["dim_company"],
          "chart_of_accounts": ["dim_account_category", "dim_account_type", "dim_account"],
          "ledger": ["fact_journal_entries", "fact_journal_lines"],
          "fiscal_periods": ["dim_fiscal_period"],
          "financial_statements": ["fact_income_statement", "fact_balance_sheet", "fact_cash_flow"]
        }
      },
      "municipal": {
        "models": {
          "entity": ["dim_municipality"],
          "funds": ["dim_fund"],
          "chart_of_accounts": ["dim_account_category", "dim_account_type", "dim_account"],
          "ledger": ["fact_journal_entries", "fact_journal_lines"],
          "fiscal_periods": ["dim_fiscal_period"],
          "programs": ["dim_program"],
          "grants": ["dim_grant", "fact_grant_expenditures"]
        }
      },
      "securities": {
        "models": {
          "securities": ["dim_security", "fact_security_prices"],
          "stocks": ["dim_stock", "fact_stock_technicals", "fact_dividends", "fact_splits"]
        }
      }
    }
  },

  "duckdb": {
    "path": "{storage_root}/duckdb/analytics.db"
  }
}
```

---

### H.8 Path Resolution

How the system resolves table references to storage paths:

```python
# Reference in YAML
from: bronze.erp.gl_journal_entries

# Resolution steps:
1. Parse: provider=erp, table=gl_journal_entries
2. Template: {storage_root}/bronze/{provider}/{table}
3. Result: /shared/storage/bronze/erp/gl_journal_entries

# Reference in query
SELECT * FROM corporate_ledger.fact_journal_entries

# Resolution steps:
1. Parse: domain=corporate, model=ledger, table=fact_journal_entries
2. Template: {storage_root}/silver/{domain}/{model}/{table}
3. Result: /shared/storage/silver/corporate/ledger/fact_journal_entries
```

---

### H.9 What Templates DON'T Create

**These paths DO NOT exist** - templates are schema definitions only:

```
# DOES NOT EXIST - templates have no storage
storage/silver/_base/                    ❌
storage/silver/_base/entities/           ❌
storage/silver/_base/accounting/         ❌

# DOES NOT EXIST - domain-base types are not built
storage/silver/accounting/journal_entry/ ❌
storage/silver/entities/person/          ❌
```

**Templates live only in the `domains/_base/` directory as YAML:**

```
domains/
├── _base/                               # YAML definitions only
│   ├── entities/
│   │   ├── entity.md                   ← Schema definition
│   │   ├── person.md                   ← Schema definition
│   │   └── organization.md             ← Schema definition
│   └── accounting/
│       ├── ledger_entity.md            ← Schema definition
│       ├── journal_entry.md            ← Schema definition
│       └── chart_of_accounts.md        ← Schema definition
│
├── corporate/                           # Built models → create storage
│   ├── company.md                      → storage/silver/corporate/company/
│   ├── ledger.md                       → storage/silver/corporate/ledger/
│   └── chart_of_accounts.md            → storage/silver/corporate/chart_of_accounts/
│
└── municipal/                           # Built models → create storage
    ├── entity.md                       → storage/silver/municipal/entity/
    ├── ledger.md                       → storage/silver/municipal/ledger/
    └── funds.md                        → storage/silver/municipal/funds/
```

---

### H.10 Storage Summary

| Location | Contains | Created By |
|----------|----------|------------|
| `domains/_base/` | YAML template definitions | Manual (schema design) |
| `domains/{category}/` | YAML model definitions | Manual (model design) |
| `storage/bronze/` | Raw ingested data | Ingestion pipeline |
| `storage/silver/` | Dimensional models | Build pipeline |
| `storage/duckdb/` | Query catalog | DuckDB (auto) |
| `configs/storage.json` | Path mappings | Manual (config) |

**Data Flow:**

```
Source Systems                domains/*.md                    storage/
     │                             │                              │
     │   ┌─────────────────────────┼──────────────────────────┐   │
     │   │                         │                          │   │
     ▼   │                         ▼                          │   ▼
┌────────┴──┐  Ingestion    ┌─────────────┐    Build    ┌─────┴────────┐
│ ERP/APIs  │ ───────────►  │   Bronze    │ ──────────► │    Silver    │
└───────────┘               │ (raw data)  │             │ (dimensional)│
                            └─────────────┘             └──────────────┘
                                  │                            │
                                  │      templates define      │
                                  │      schema structure      │
                                  │             │              │
                                  │             ▼              │
                                  │    ┌───────────────┐       │
                                  │    │ domains/_base │       │
                                  │    │ (YAML only)   │       │
                                  │    └───────────────┘       │
                                  │                            │
                                  └────────────┬───────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │   DuckDB    │
                                        │  (queries)  │
                                        └─────────────┘
```

---

## Appendix I: Cross-Domain Aggregation Patterns

This appendix addresses a key architectural question: **How do you query across domains that share a common base template?**

For example, if both `corporate_ledger` and `municipal_ledger` extend `_base.accounting.ledger`, can you aggregate across both in a single query?

### The Challenge

Base templates (`domains/_base/`) define schema structure but **don't create storage**:

```
domains/_base/accounting/ledger.md     → NO storage (template only)
domains/corporate/ledger.md            → storage/silver/corporate/ledger/
domains/municipal/ledger.md            → storage/silver/municipal/ledger/
```

There is no "unified ledger table" to query against. Each domain has its own separate tables.

### Three Solutions

| Approach | Complexity | Best For |
|----------|------------|----------|
| **Option 1: UNION View** | Low | Ad-hoc analysis, reporting |
| **Option 2: Cross-Domain Model** | Medium | Permanent unified analytics |
| **Option 3: Enhanced `extends:` with Auto-Federation** | Low (after implementation) | Automatic cross-domain queries |

---

### I.1 Option 1: UNION View Pattern

Create a SQL view that unions tables from multiple domains.

#### I.1.1 View Definition

```sql
-- Create in DuckDB analytics.db or as a managed view
CREATE OR REPLACE VIEW unified_ledger AS

-- Corporate ledger entries
SELECT
    'corporate' AS domain,
    'CORP' AS domain_code,
    je.journal_entry_id,
    je.journal_number,
    je.ledger_entity_id AS entity_id,
    c.company_name AS entity_name,
    je.posting_date_id,
    je.fiscal_period_id,
    je.journal_type,
    je.entry_status,
    je.total_debits,
    je.total_credits,
    je.is_balanced,
    je.source_system,
    je.created_timestamp
FROM corporate_ledger.fact_journal_entries je
JOIN corporate.company.dim_company c ON je.ledger_entity_id = c.company_id

UNION ALL

-- Municipal ledger entries
SELECT
    'municipal' AS domain,
    'MUNI' AS domain_code,
    je.journal_entry_id,
    je.journal_number,
    je.ledger_entity_id AS entity_id,
    m.municipality_name AS entity_name,
    je.posting_date_id,
    je.fiscal_period_id,
    je.journal_type,
    je.entry_status,
    je.total_debits,
    je.total_credits,
    je.is_balanced,
    je.source_system,
    je.created_timestamp
FROM municipal_ledger.fact_journal_entries je
JOIN municipal.entity.dim_municipality m ON je.ledger_entity_id = m.municipality_id;
```

#### I.1.2 Unified Line Items View

```sql
CREATE OR REPLACE VIEW unified_ledger_lines AS

SELECT
    'corporate' AS domain,
    jl.line_id,
    jl.journal_entry_id,
    jl.line_number,
    jl.account_id,
    a.account_code,
    a.account_name,
    cat.category_name AS account_category,
    jl.debit,
    jl.credit,
    jl.net_amount,
    jl.description,
    jl.posting_date_id
FROM corporate_ledger.fact_journal_lines jl
JOIN corporate.chart_of_accounts.dim_account a ON jl.account_id = a.account_id
JOIN corporate.chart_of_accounts.dim_account_category cat ON a.category_id = cat.category_id

UNION ALL

SELECT
    'municipal' AS domain,
    jl.line_id,
    jl.journal_entry_id,
    jl.line_number,
    jl.account_id,
    a.account_code,
    a.account_name,
    cat.category_name AS account_category,
    jl.debit,
    jl.credit,
    jl.net_amount,
    jl.description,
    jl.posting_date_id
FROM municipal_ledger.fact_journal_lines jl
JOIN municipal.chart_of_accounts.dim_account a ON jl.account_id = a.account_id
JOIN municipal.chart_of_accounts.dim_account_category cat ON a.category_id = cat.category_id;
```

#### I.1.3 Query Examples

```sql
-- Compare balances by domain and account category
SELECT
    domain,
    account_category,
    SUM(debit) AS total_debits,
    SUM(credit) AS total_credits,
    SUM(net_amount) AS net_balance
FROM unified_ledger_lines
WHERE posting_date_id BETWEEN 20250101 AND 20251231
GROUP BY domain, account_category
ORDER BY domain, account_category;
```

**Result:**

| domain | account_category | total_debits | total_credits | net_balance |
|--------|------------------|--------------|---------------|-------------|
| corporate | Assets | 15,000,000 | 12,000,000 | 3,000,000 |
| corporate | Liabilities | 8,000,000 | 10,000,000 | -2,000,000 |
| corporate | Revenue | 500,000 | 25,000,000 | -24,500,000 |
| municipal | Assets | 45,000,000 | 40,000,000 | 5,000,000 |
| municipal | Liabilities | 20,000,000 | 22,000,000 | -2,000,000 |
| municipal | Revenue | 1,000,000 | 120,000,000 | -119,000,000 |

```sql
-- Cross-domain totals
SELECT
    account_category,
    SUM(CASE WHEN domain = 'corporate' THEN net_balance END) AS corporate,
    SUM(CASE WHEN domain = 'municipal' THEN net_balance END) AS municipal,
    SUM(net_balance) AS combined_total
FROM (
    SELECT
        domain,
        account_category,
        SUM(net_amount) AS net_balance
    FROM unified_ledger_lines
    WHERE posting_date_id BETWEEN 20250101 AND 20251231
    GROUP BY domain, account_category
) sub
GROUP BY account_category;
```

#### I.1.4 View Management Template

```yaml
# domains/enterprise/unified_views.md
---
type: domain-views
model: unified_views
description: "Cross-domain UNION views for enterprise reporting"

views:
  unified_ledger:
    description: "Combined journal entries from all ledger domains"
    sources:
      - corporate_ledger.fact_journal_entries
      - municipal_ledger.fact_journal_entries
    discriminator: domain

  unified_ledger_lines:
    description: "Combined journal lines with account details"
    sources:
      - corporate_ledger.fact_journal_lines
      - municipal_ledger.fact_journal_lines
    discriminator: domain
    joins:
      - to: "{domain}.chart_of_accounts.dim_account"
        on: account_id

  unified_trial_balance:
    description: "Combined trial balance across domains"
    type: aggregate
    source: unified_ledger_lines
    group_by: [domain, account_category, account_code]
    measures:
      - total_debits
      - total_credits
      - net_balance

storage:
  # Views don't create storage - they're query definitions
  type: view
  catalog: duckdb
---

## Unified Views

These views provide cross-domain querying capability without duplicating data.

### Usage

```python
from de_funk.core.session import UniversalSession

session = UniversalSession(backend="duckdb")

# Query unified view
df = session.query("""
    SELECT domain, account_category, SUM(net_amount) as balance
    FROM unified_ledger_lines
    GROUP BY domain, account_category
""")
```
```

#### I.1.5 Process Flow: UNION View

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         UNION View Pattern                               │
└─────────────────────────────────────────────────────────────────────────┘

  domains/_base/                    domains/{category}/
       │                                    │
       │  Schema Template                   │  Domain Models
       ▼                                    ▼
┌─────────────────┐              ┌─────────────────────┐
│ _base.accounting│              │ corporate/ledger.md │
│    .ledger      │◄─── extends ─│ municipal/ledger.md │
│                 │              │                     │
└─────────────────┘              └──────────┬──────────┘
                                            │
                                            │ Build Pipeline
                                            ▼
                           ┌─────────────────────────────────┐
                           │         storage/silver/          │
                           │                                   │
                           │  corporate/ledger/                │
                           │    └── fact_journal_entries/      │
                           │    └── fact_journal_lines/        │
                           │                                   │
                           │  municipal/ledger/                │
                           │    └── fact_journal_entries/      │
                           │    └── fact_journal_lines/        │
                           └──────────────┬────────────────────┘
                                          │
                                          │ View Creation
                                          ▼
                           ┌─────────────────────────────────┐
                           │        DuckDB Catalog            │
                           │                                   │
                           │  CREATE VIEW unified_ledger AS   │
                           │    SELECT ... FROM corporate...  │
                           │    UNION ALL                     │
                           │    SELECT ... FROM municipal...  │
                           └──────────────┬────────────────────┘
                                          │
                                          │ Query
                                          ▼
                           ┌─────────────────────────────────┐
                           │     SELECT * FROM unified_ledger │
                           │     WHERE domain = 'corporate'   │
                           │        OR account_category = ... │
                           └─────────────────────────────────┘
```

---

### I.2 Option 2: Cross-Domain Model Pattern

Create a dedicated domain model that explicitly references and combines data from multiple source domains.

#### I.2.1 Enterprise Ledger Model Template

```yaml
# domains/enterprise/unified_ledger.md
---
type: domain-model
model: unified_ledger
description: "Enterprise-wide unified ledger combining corporate and municipal"
version: "1.0"

# This model depends on both domain ledgers
depends_on:
  - temporal
  - corporate_ledger
  - municipal_ledger
  - corporate.chart_of_accounts
  - municipal.chart_of_accounts

# No bronze source - this is a Silver-to-Silver model
sources:
  type: silver
  domains:
    - corporate_ledger
    - municipal_ledger

tables:
  # Unified journal entries fact table
  fact_unified_entries:
    type: fact
    description: "Combined journal entries from all accounting domains"
    primary_key: [unified_entry_id]
    partition_by: [posting_date_id]

    # Build from multiple sources
    from:
      type: union
      sources:
        - source: corporate_ledger.fact_journal_entries
          domain_code: CORP
          entity_join:
            table: corporate.company.dim_company
            key: company_id
            name_field: company_name

        - source: municipal_ledger.fact_journal_entries
          domain_code: MUNI
          entity_join:
            table: municipal.entity.dim_municipality
            key: municipality_id
            name_field: municipality_name

    schema:
      # === IDENTITY ===
      - [unified_entry_id, integer, false, "PK - computed from domain + source ID"]
      - [source_domain, string, false, "Source domain", {enum: [corporate, municipal]}]
      - [domain_code, string, false, "Short domain code", {enum: [CORP, MUNI]}]
      - [source_entry_id, integer, false, "Original entry ID from source domain"]

      # === ENTITY (normalized across domains) ===
      - [entity_id, integer, false, "Normalized entity ID"]
      - [entity_name, string, false, "Entity name from source domain"]
      - [entity_type, string, false, "Company, Municipality, etc."]

      # === INHERITED FROM BASE LEDGER ===
      - [journal_number, string, false, "Journal entry number"]
      - [posting_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [fiscal_period_id, integer, true, "FK to fiscal period"]
      - [transaction_date_id, integer, true, "FK to calendar"]
      - [journal_type, string, true, "Journal type"]
      - [entry_status, string, false, "Entry status"]
      - [total_debits, double, false, "Sum of debit amounts"]
      - [total_credits, double, false, "Sum of credit amounts"]
      - [is_balanced, boolean, false, "Debits equal credits"]

      # === AUDIT ===
      - [source_system, string, true, "Originating system"]
      - [created_timestamp, timestamp, true, "When created"]

    # Key computation for unified_entry_id
    derived_columns:
      unified_entry_id: "ABS(HASH(CONCAT(source_domain, '_', source_entry_id)))"
      entity_type: "CASE WHEN source_domain = 'corporate' THEN 'Company' ELSE 'Municipality' END"

    measures:
      - [entry_count, count_distinct, unified_entry_id, "Total entries", {format: "#,##0"}]
      - [corporate_entries, count_distinct, unified_entry_id, "Corporate entries", {format: "#,##0", filter: "source_domain = 'corporate'"}]
      - [municipal_entries, count_distinct, unified_entry_id, "Municipal entries", {format: "#,##0", filter: "source_domain = 'municipal'"}]
      - [total_debits, sum, total_debits, "Total debits", {format: "$#,##0.00"}]
      - [total_credits, sum, total_credits, "Total credits", {format: "$#,##0.00"}]

  # Unified journal lines fact table
  fact_unified_lines:
    type: fact
    description: "Combined journal lines from all accounting domains"
    primary_key: [unified_line_id]
    partition_by: [posting_date_id]

    from:
      type: union
      sources:
        - source: corporate_ledger.fact_journal_lines
          domain_code: CORP
        - source: municipal_ledger.fact_journal_lines
          domain_code: MUNI

    schema:
      # === IDENTITY ===
      - [unified_line_id, integer, false, "PK"]
      - [unified_entry_id, integer, false, "FK to unified entries", {fk: fact_unified_entries.unified_entry_id}]
      - [source_domain, string, false, "Source domain"]
      - [source_line_id, integer, false, "Original line ID"]

      # === LINE DATA ===
      - [line_number, integer, false, "Line number within entry"]
      - [account_id, integer, false, "FK to account (domain-specific)"]
      - [account_code, string, false, "Account code (denormalized)"]
      - [account_name, string, false, "Account name (denormalized)"]
      - [account_category, string, false, "Category (denormalized)"]
      - [debit, double, true, "Debit amount"]
      - [credit, double, true, "Credit amount"]
      - [net_amount, double, false, "Debit - Credit"]
      - [description, string, true, "Line description"]
      - [posting_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]

    measures:
      - [line_count, count_distinct, unified_line_id, "Total lines", {format: "#,##0"}]
      - [total_debits, sum, debit, "Total debits", {format: "$#,##0.00"}]
      - [total_credits, sum, credit, "Total credits", {format: "$#,##0.00"}]
      - [net_balance, sum, net_amount, "Net balance", {format: "$#,##0.00"}]

  # Enterprise trial balance (aggregated)
  fact_trial_balance:
    type: fact
    description: "Pre-aggregated trial balance by domain and account"
    primary_key: [trial_balance_id]
    partition_by: [fiscal_period_id]

    from:
      type: aggregate
      source: fact_unified_lines
      group_by: [source_domain, fiscal_period_id, account_category, account_code]

    schema:
      - [trial_balance_id, integer, false, "PK"]
      - [source_domain, string, false, "Domain"]
      - [fiscal_period_id, integer, false, "FK to fiscal period"]
      - [account_category, string, false, "Account category"]
      - [account_code, string, false, "Account code"]
      - [account_name, string, false, "Account name"]
      - [period_debits, double, false, "Total debits for period"]
      - [period_credits, double, false, "Total credits for period"]
      - [period_net, double, false, "Net for period"]
      - [ytd_debits, double, true, "Year-to-date debits"]
      - [ytd_credits, double, true, "Year-to-date credits"]
      - [ytd_net, double, true, "Year-to-date net"]

graph:
  nodes:
    fact_unified_entries:
      from: computed
    fact_unified_lines:
      from: computed
    fact_trial_balance:
      from: computed

  edges:
    - [fact_unified_lines, fact_unified_entries, unified_entry_id]
    - [fact_unified_entries, temporal.dim_calendar, posting_date_id:date_id]
    - [fact_unified_lines, temporal.dim_calendar, posting_date_id:date_id]

  paths:
    entries_by_date:
      description: "Unified entries with calendar details"
      via: [fact_unified_entries, temporal.dim_calendar]

    lines_detail:
      description: "Line items with entry and calendar"
      via: [fact_unified_lines, fact_unified_entries, temporal.dim_calendar]

storage:
  format: delta
  silver:
    root: storage/silver/enterprise/unified_ledger
    tables:
      - fact_unified_entries
      - fact_unified_lines
      - fact_trial_balance

status: active
---

## Enterprise Unified Ledger

This model combines accounting data from multiple domains into a single queryable structure.

### Why Use This Pattern?

| Benefit | Description |
|---------|-------------|
| **Pre-computed** | Data is materialized, not computed at query time |
| **Indexed** | Can add domain-specific indexes |
| **Partitioned** | Consistent partitioning across all source data |
| **Aggregates** | Pre-built trial balance for fast reporting |

### Build Process

```bash
# Build depends on source models being current
python -m scripts.build.build_models --models unified_ledger

# Runs after corporate_ledger and municipal_ledger are built
```

### Query Examples

```sql
-- Compare domains by category
SELECT
    source_domain,
    account_category,
    SUM(period_net) AS balance
FROM unified_ledger.fact_trial_balance
WHERE fiscal_period_id = 202501
GROUP BY source_domain, account_category;

-- Drill into specific entries
SELECT
    e.entity_name,
    e.journal_number,
    l.account_name,
    l.debit,
    l.credit
FROM unified_ledger.fact_unified_entries e
JOIN unified_ledger.fact_unified_lines l USING (unified_entry_id)
WHERE e.source_domain = 'municipal'
  AND e.posting_date_id = 20250115;
```
```

#### I.2.2 Builder Implementation

```python
# de_funk/models/builders/union_builder.py
"""
Builder for cross-domain UNION models.
"""
from typing import List, Dict
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import lit, concat, abs as spark_abs, hash as spark_hash

class UnionBuilder:
    """Builds tables from multiple source domains."""

    def __init__(self, spark: SparkSession, model_config: dict):
        self.spark = spark
        self.config = model_config

    def build_union_table(self, table_config: dict) -> DataFrame:
        """Build a table by unioning multiple sources."""

        union_config = table_config['from']
        sources = union_config['sources']

        dfs = []
        for source in sources:
            source_path = self._resolve_source_path(source['source'])
            df = self.spark.read.format('delta').load(source_path)

            # Add domain discriminator
            df = df.withColumn('source_domain', lit(source['source'].split('.')[0]))
            df = df.withColumn('domain_code', lit(source['domain_code']))

            # Rename source ID column
            source_id_col = self._get_primary_key(source['source'])
            df = df.withColumnRenamed(source_id_col, 'source_entry_id')

            # Handle entity join if specified
            if 'entity_join' in source:
                entity_config = source['entity_join']
                entity_df = self.spark.read.format('delta').load(
                    self._resolve_source_path(entity_config['table'])
                )
                df = df.join(
                    entity_df.select(
                        entity_config['key'],
                        entity_config['name_field']
                    ).withColumnRenamed(entity_config['name_field'], 'entity_name'),
                    df['ledger_entity_id'] == entity_df[entity_config['key']],
                    'left'
                )

            dfs.append(df)

        # Union all sources
        result = dfs[0]
        for df in dfs[1:]:
            result = result.unionByName(df, allowMissingColumns=True)

        # Add computed columns
        if 'derived_columns' in table_config:
            for col_name, expression in table_config['derived_columns'].items():
                result = result.withColumn(col_name, expr(expression))

        return result

    def _resolve_source_path(self, source_ref: str) -> str:
        """Resolve a source reference to a storage path."""
        parts = source_ref.split('.')
        if len(parts) == 2:
            # model.table format
            model, table = parts
            return f"storage/silver/{model}/{table}"
        elif len(parts) == 3:
            # domain.model.table format
            domain, model, table = parts
            return f"storage/silver/{domain}/{model}/{table}"
        raise ValueError(f"Invalid source reference: {source_ref}")
```

#### I.2.3 Process Flow: Cross-Domain Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Cross-Domain Model Pattern                           │
└─────────────────────────────────────────────────────────────────────────┘

                         Source Domain Models
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ corporate_ledger │   │ municipal_ledger│   │   (future...)   │
│                 │   │                 │   │                 │
│ fact_journal_*  │   │ fact_journal_*  │   │                 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         │   storage/silver/   │                     │
         │   corporate/ledger/ │                     │
         │                     │                     │
         └──────────┬──────────┴──────────┬──────────┘
                    │                     │
                    │  UnionBuilder       │
                    │  reads all sources  │
                    ▼                     │
         ┌─────────────────────────────────────────┐
         │         domains/enterprise/             │
         │         unified_ledger.md               │
         │                                          │
         │  type: domain-model                      │
         │  from:                                   │
         │    type: union                           │
         │    sources:                              │
         │      - corporate_ledger.fact_*          │
         │      - municipal_ledger.fact_*          │
         └──────────────────┬──────────────────────┘
                            │
                            │ Build Pipeline
                            ▼
         ┌─────────────────────────────────────────┐
         │    storage/silver/enterprise/           │
         │         unified_ledger/                 │
         │                                          │
         │    fact_unified_entries/                │
         │    fact_unified_lines/                  │
         │    fact_trial_balance/                  │
         └──────────────────┬──────────────────────┘
                            │
                            │ Query
                            ▼
         ┌─────────────────────────────────────────┐
         │  SELECT * FROM unified_ledger           │
         │     .fact_unified_entries               │
         │  WHERE source_domain IN ('corporate',   │
         │                          'municipal')   │
         └─────────────────────────────────────────┘
```

#### I.2.4 Storage Structure

```
storage/silver/
├── corporate/
│   └── ledger/
│       ├── fact_journal_entries/       # Source data
│       └── fact_journal_lines/
│
├── municipal/
│   └── ledger/
│       ├── fact_journal_entries/       # Source data
│       └── fact_journal_lines/
│
└── enterprise/                          # NEW: Cross-domain model
    └── unified_ledger/
        ├── fact_unified_entries/        # Materialized union
        │   ├── _delta_log/
        │   ├── posting_date_id=20250101/
        │   └── ...
        ├── fact_unified_lines/          # Materialized union
        │   └── ...
        └── fact_trial_balance/          # Pre-aggregated
            └── ...
```

---

### I.3 Option 3: Enhanced `extends:` with Auto-Federation

This pattern enhances the `extends:` keyword to automatically create federated views across all models that share a common base template.

#### I.3.1 Enhanced Base Template

```yaml
# domains/_base/accounting/ledger.md
---
type: domain-base
base_name: ledger
description: "Base ledger template with auto-federation"
version: "2.0"

# NEW: Federation configuration
federation:
  enabled: true
  view_name: federated_ledger           # Auto-created view name
  discriminator_column: domain          # Column added to identify source
  discriminator_format: "{model_name}"  # Value pattern (e.g., "corporate_ledger")

  # Tables to include in federation
  federated_tables:
    - _fact_journal_entries
    - _fact_journal_lines

  # Optional: Pre-built aggregate views
  aggregate_views:
    - name: federated_trial_balance
      source: _fact_journal_lines
      group_by: [domain, fiscal_period_id, account_category]
      measures: [total_debits, total_credits, net_balance]

# Standard base template schema
tables:
  _fact_journal_entries:
    type: fact
    primary_key: [journal_entry_id]
    partition_by: [posting_date_id]

    schema:
      - [journal_entry_id, integer, false, "PK - surrogate"]
      - [journal_number, string, false, "Natural key"]
      - [ledger_entity_id, integer, false, "FK to entity dimension"]
      - [posting_date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [fiscal_period_id, integer, true, "FK to fiscal period"]
      - [transaction_date_id, integer, true, "FK to calendar"]
      - [journal_type, string, true, "Standard, Adjusting, Closing, etc."]
      - [entry_status, string, false, "Draft, Posted, Reversed"]
      - [total_debits, double, false, "Sum of line debits"]
      - [total_credits, double, false, "Sum of line credits"]
      - [is_balanced, boolean, false, "Debits = Credits"]
      - [source_system, string, true, "Originating system"]
      - [source_id, string, true, "ID in source system"]
      - [created_timestamp, timestamp, true, "Record creation time"]

    measures:
      - [entry_count, count_distinct, journal_entry_id, "Total entries", {format: "#,##0"}]
      - [total_debits, sum, total_debits, "Total debits", {format: "$#,##0.00"}]
      - [total_credits, sum, total_credits, "Total credits", {format: "$#,##0.00"}]

  _fact_journal_lines:
    type: fact
    primary_key: [line_id]
    partition_by: [posting_date_id]

    schema:
      - [line_id, integer, false, "PK"]
      - [journal_entry_id, integer, false, "FK to entry", {fk: _fact_journal_entries.journal_entry_id}]
      - [line_number, integer, false, "Line sequence"]
      - [account_id, integer, false, "FK to chart of accounts"]
      - [cost_center_id, integer, true, "FK to cost center"]
      - [debit, double, true, "Debit amount"]
      - [credit, double, true, "Credit amount"]
      - [net_amount, double, false, "Debit - Credit", {derive: "COALESCE(debit, 0) - COALESCE(credit, 0)"}]
      - [description, string, true, "Line description"]
      - [posting_date_id, integer, false, "FK to calendar"]

    measures:
      - [line_count, count_distinct, line_id, "Total lines", {format: "#,##0"}]
      - [total_debits, sum, debit, "Total debits", {format: "$#,##0.00"}]
      - [total_credits, sum, credit, "Total credits", {format: "$#,##0.00"}]
      - [net_balance, sum, net_amount, "Net balance", {format: "$#,##0.00"}]

status: active
---

## Base Ledger Template with Federation

This template provides the standard accounting ledger structure AND automatically
creates federated views across all domains that extend it.

### Federation Behavior

When you run the build pipeline:

1. Builder identifies all models extending `_base.accounting.ledger`
2. For each model found, it registers the model name
3. After all models are built, it creates federated views:

```sql
-- Auto-generated federated view
CREATE VIEW federated_ledger.fact_journal_entries AS
SELECT 'corporate_ledger' AS domain, * FROM corporate_ledger.fact_journal_entries
UNION ALL
SELECT 'municipal_ledger' AS domain, * FROM municipal_ledger.fact_journal_entries;
```

### No Code Required

Child models just use `extends:` normally - federation is automatic:

```yaml
# domains/corporate/ledger.md
extends: _base.accounting.ledger
# ↑ Automatically joins the federation
```
```

#### I.3.2 Child Model (Unchanged)

```yaml
# domains/corporate/ledger.md
---
type: domain-model
model: corporate_ledger
description: "Corporate general ledger"
version: "2.0"

# This single line enables federation
extends: _base.accounting.ledger

depends_on:
  - temporal
  - corporate.company
  - corporate.chart_of_accounts

tables:
  fact_journal_entries:
    # Inherits all schema from base template
    # Just add corporate-specific columns
    from: bronze.erp.gl_journal_entries

    schema:
      # Corporate-specific additions
      - [company_id, integer, false, "FK to company", {fk: corporate.company.dim_company.company_id}]
      - [department_id, integer, true, "FK to department"]
      - [project_id, integer, true, "FK to project"]

  fact_journal_lines:
    from: bronze.erp.gl_journal_lines
    # Inherits all base schema
    # Can add corporate-specific columns

storage:
  format: delta
  bronze:
    provider: erp
  silver:
    root: storage/silver/corporate/ledger

status: active
---

## Corporate Ledger

General ledger for corporate entities.

### Federation

This model automatically participates in the `federated_ledger` view because
it extends `_base.accounting.ledger` which has `federation.enabled: true`.
```

```yaml
# domains/municipal/ledger.md
---
type: domain-model
model: municipal_ledger
description: "Municipal general ledger with fund accounting"
version: "2.0"

# Also joins the federation automatically
extends: _base.accounting.ledger

depends_on:
  - temporal
  - municipal.entity
  - municipal.funds
  - municipal.chart_of_accounts

tables:
  fact_journal_entries:
    from: bronze.munis.gl_journal_entries

    schema:
      # Municipal-specific additions
      - [municipality_id, integer, false, "FK to municipality", {fk: municipal.entity.dim_municipality.municipality_id}]
      - [fund_id, integer, false, "FK to fund", {fk: municipal.funds.dim_fund.fund_id}]
      - [program_id, integer, true, "FK to program"]
      - [grant_id, integer, true, "FK to grant"]

  fact_journal_lines:
    from: bronze.munis.gl_journal_lines

    schema:
      # Municipal-specific: fund accounting columns
      - [fund_id, integer, false, "FK to fund"]
      - [function_code, string, true, "GASB function code"]
      - [object_code, string, true, "Expenditure object code"]

storage:
  format: delta
  bronze:
    provider: munis
  silver:
    root: storage/silver/municipal/ledger

status: active
---

## Municipal Ledger

General ledger for municipal entities with GASB-compliant fund accounting.
```

#### I.3.3 Federation Builder Implementation

```python
# de_funk/models/builders/federation_builder.py
"""
Builds federated views for base templates with federation enabled.
"""
from typing import Dict, List, Set
from pathlib import Path
import yaml

class FederationRegistry:
    """Tracks models that extend federated base templates."""

    def __init__(self):
        # base_template -> set of child models
        self._registry: Dict[str, Set[str]] = {}
        # base_template -> federation config
        self._configs: Dict[str, dict] = {}

    def register_base(self, base_name: str, federation_config: dict):
        """Register a base template with federation enabled."""
        self._registry[base_name] = set()
        self._configs[base_name] = federation_config

    def register_child(self, base_name: str, model_name: str):
        """Register a child model that extends a federated base."""
        if base_name in self._registry:
            self._registry[base_name].add(model_name)

    def get_children(self, base_name: str) -> Set[str]:
        """Get all models extending a base template."""
        return self._registry.get(base_name, set())

    def get_federation_config(self, base_name: str) -> dict:
        """Get federation config for a base template."""
        return self._configs.get(base_name, {})


class FederationBuilder:
    """Builds federated views after all domain models are built."""

    def __init__(self, registry: FederationRegistry, session):
        self.registry = registry
        self.session = session  # DuckDB or Spark session

    def build_all_federations(self):
        """Build federated views for all registered base templates."""

        for base_name, children in self.registry._registry.items():
            if not children:
                continue

            config = self.registry.get_federation_config(base_name)
            self._build_federation(base_name, children, config)

    def _build_federation(self, base_name: str, children: Set[str], config: dict):
        """Build federated views for a single base template."""

        view_name = config.get('view_name', f'federated_{base_name}')
        discriminator = config.get('discriminator_column', 'domain')
        tables = config.get('federated_tables', [])

        for table in tables:
            # Remove leading underscore from base table name
            table_name = table.lstrip('_')

            # Build UNION query
            union_parts = []
            for child_model in sorted(children):
                # Get domain value
                domain_value = config.get('discriminator_format', '{model_name}').format(
                    model_name=child_model
                )

                union_parts.append(f"""
                    SELECT
                        '{domain_value}' AS {discriminator},
                        *
                    FROM {child_model}.{table_name}
                """)

            union_sql = "\nUNION ALL\n".join(union_parts)

            # Create the view
            create_view_sql = f"""
                CREATE OR REPLACE VIEW {view_name}.{table_name} AS
                {union_sql}
            """

            self.session.execute(create_view_sql)
            print(f"Created federated view: {view_name}.{table_name}")

        # Build aggregate views if specified
        for agg_view in config.get('aggregate_views', []):
            self._build_aggregate_view(view_name, agg_view, discriminator)

    def _build_aggregate_view(self, schema: str, config: dict, discriminator: str):
        """Build a pre-aggregated view."""

        source_table = config['source'].lstrip('_')
        group_cols = [discriminator] + config['group_by']

        # Build measure expressions
        measure_exprs = []
        for measure in config['measures']:
            if measure == 'total_debits':
                measure_exprs.append("SUM(debit) AS total_debits")
            elif measure == 'total_credits':
                measure_exprs.append("SUM(credit) AS total_credits")
            elif measure == 'net_balance':
                measure_exprs.append("SUM(COALESCE(debit, 0) - COALESCE(credit, 0)) AS net_balance")

        sql = f"""
            CREATE OR REPLACE VIEW {schema}.{config['name']} AS
            SELECT
                {', '.join(group_cols)},
                {', '.join(measure_exprs)}
            FROM {schema}.{source_table}
            GROUP BY {', '.join(group_cols)}
        """

        self.session.execute(sql)
        print(f"Created aggregate view: {schema}.{config['name']}")
```

#### I.3.4 Build Pipeline Integration

```python
# de_funk/models/builders/model_builder.py (excerpt)

class ModelBuilder:
    """Main builder that orchestrates domain model builds."""

    def __init__(self, spark, config_loader):
        self.spark = spark
        self.config_loader = config_loader
        self.federation_registry = FederationRegistry()

    def build_all(self):
        """Build all domain models and federated views."""

        # Phase 1: Discover and register federations
        self._discover_federations()

        # Phase 2: Build individual domain models
        for model_name in self._get_build_order():
            self._build_model(model_name)

        # Phase 3: Build federated views
        self._build_federations()

    def _discover_federations(self):
        """Scan base templates for federation configs."""

        base_path = Path("domains/_base")
        for md_file in base_path.rglob("*.md"):
            config = self.config_loader.load_base_template(md_file)

            if config.get('federation', {}).get('enabled'):
                base_name = config['base_name']
                self.federation_registry.register_base(
                    base_name,
                    config['federation']
                )

    def _build_model(self, model_name: str):
        """Build a single domain model."""

        config = self.config_loader.load_model_config(model_name)

        # Register with federation if extends a federated base
        if 'extends' in config:
            base_ref = config['extends']
            base_name = base_ref.split('.')[-1]  # e.g., "_base.accounting.ledger" -> "ledger"
            self.federation_registry.register_child(base_name, model_name)

        # ... rest of build logic ...

    def _build_federations(self):
        """Build federated views after all models are built."""

        from de_funk.core.session import UniversalSession

        session = UniversalSession(backend="duckdb")
        builder = FederationBuilder(self.federation_registry, session)
        builder.build_all_federations()
```

#### I.3.5 Process Flow: Auto-Federation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Auto-Federation via extends:                          │
└─────────────────────────────────────────────────────────────────────────┘

Phase 1: Discovery
──────────────────

domains/_base/accounting/ledger.md
┌─────────────────────────────────┐
│ federation:                     │
│   enabled: true                 │◄─── Builder finds this
│   view_name: federated_ledger   │
│   federated_tables:             │
│     - _fact_journal_entries     │
│     - _fact_journal_lines       │
└─────────────────────────────────┘
              │
              │ Register base template
              ▼
┌─────────────────────────────────┐
│     FederationRegistry          │
│                                 │
│ ledger:                         │
│   children: []  ← empty         │
│   config: {enabled: true, ...}  │
└─────────────────────────────────┘


Phase 2: Build Domain Models
────────────────────────────

domains/corporate/ledger.md          domains/municipal/ledger.md
┌────────────────────────┐           ┌────────────────────────┐
│ extends: _base...ledger│           │ extends: _base...ledger│
└───────────┬────────────┘           └───────────┬────────────┘
            │                                    │
            │ Register as child                  │
            ▼                                    ▼
┌─────────────────────────────────────────────────────────────┐
│     FederationRegistry                                       │
│                                                              │
│ ledger:                                                      │
│   children: [corporate_ledger, municipal_ledger]  ← filled  │
│   config: {enabled: true, ...}                               │
└─────────────────────────────────────────────────────────────┘
            │
            │ Build Silver tables
            ▼
┌─────────────────────────────────────────────────────────────┐
│ storage/silver/                                              │
│   corporate/ledger/fact_journal_entries/                    │
│   corporate/ledger/fact_journal_lines/                      │
│   municipal/ledger/fact_journal_entries/                    │
│   municipal/ledger/fact_journal_lines/                      │
└─────────────────────────────────────────────────────────────┘


Phase 3: Build Federations
──────────────────────────

┌─────────────────────────────────────────────────────────────┐
│     FederationBuilder                                        │
│                                                              │
│ For each base with children:                                 │
│   1. Get all registered children                             │
│   2. Build UNION view across all                             │
│   3. Add discriminator column                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ Auto-generate views
                           ▼
┌─────────────────────────────────────────────────────────────┐
│     DuckDB Catalog                                           │
│                                                              │
│ CREATE VIEW federated_ledger.fact_journal_entries AS        │
│   SELECT 'corporate_ledger' AS domain, *                    │
│   FROM corporate_ledger.fact_journal_entries                │
│   UNION ALL                                                  │
│   SELECT 'municipal_ledger' AS domain, *                    │
│   FROM municipal_ledger.fact_journal_entries;               │
│                                                              │
│ CREATE VIEW federated_ledger.fact_journal_lines AS          │
│   SELECT 'corporate_ledger' AS domain, *                    │
│   FROM corporate_ledger.fact_journal_lines                  │
│   UNION ALL                                                  │
│   SELECT 'municipal_ledger' AS domain, *                    │
│   FROM municipal_ledger.fact_journal_lines;                 │
└─────────────────────────────────────────────────────────────┘


Phase 4: Query
──────────────

┌─────────────────────────────────────────────────────────────┐
│  SELECT                                                      │
│      domain,                                                 │
│      SUM(total_debits) as debits,                           │
│      SUM(total_credits) as credits                          │
│  FROM federated_ledger.fact_journal_entries                 │
│  WHERE posting_date_id BETWEEN 20250101 AND 20251231        │
│  GROUP BY domain;                                            │
│                                                              │
│  ┌─────────────────┬────────────────┬────────────────┐      │
│  │ domain          │ debits         │ credits        │      │
│  ├─────────────────┼────────────────┼────────────────┤      │
│  │ corporate_ledger│ 150,000,000.00 │ 150,000,000.00 │      │
│  │ municipal_ledger│ 450,000,000.00 │ 450,000,000.00 │      │
│  └─────────────────┴────────────────┴────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

### I.4 Comparison of Approaches

| Feature | UNION View | Cross-Domain Model | Auto-Federation |
|---------|------------|-------------------|-----------------|
| **Complexity** | Low | Medium | Low (after impl) |
| **Storage** | None (view only) | Duplicates data | None (view only) |
| **Performance** | Query-time UNION | Pre-materialized | Query-time UNION |
| **Maintenance** | Manual SQL | Manual YAML | Automatic |
| **New Domain** | Update SQL | Update YAML | Just use `extends:` |
| **Aggregates** | Manual views | Built-in | Configurable |
| **Use Case** | Ad-hoc, prototyping | Production reporting | Scalable enterprise |

### I.5 Recommendation

| Scenario | Recommended Approach |
|----------|---------------------|
| **Quick analysis** | Option 1: UNION View |
| **Production dashboards** | Option 2: Cross-Domain Model |
| **Many domains, evolving** | Option 3: Auto-Federation |
| **Mixed requirements** | Combine: Auto-federation + materialized aggregates |

### I.6 Complete Example: Adding a New Domain

To add a new domain (e.g., "nonprofit_ledger") to an auto-federated system:

```yaml
# domains/nonprofit/ledger.md
---
type: domain-model
model: nonprofit_ledger
extends: _base.accounting.ledger  # ← That's it!

depends_on:
  - temporal
  - nonprofit.organization

tables:
  fact_journal_entries:
    from: bronze.nfp.gl_journal_entries
    schema:
      - [org_id, integer, false, "FK to nonprofit org"]
      - [grant_id, integer, true, "FK to grant"]
      - [restriction_type, string, true, "Unrestricted, Temp, Permanent"]

storage:
  silver:
    root: storage/silver/nonprofit/ledger
---
```

**Result after build:**
- New Silver tables: `storage/silver/nonprofit/ledger/`
- Federated views automatically updated to include `nonprofit_ledger`
- No SQL changes required
- No manual view updates

```sql
-- Automatically includes the new domain
SELECT domain, COUNT(*) as entries
FROM federated_ledger.fact_journal_entries
GROUP BY domain;

-- Returns:
-- corporate_ledger  | 500,000
-- municipal_ledger  | 2,000,000
-- nonprofit_ledger  | 150,000   ← Automatically included
```
