# Graph Architecture

**YAML-driven graph-based dimensional modeling**

---

## Overview

de_Funk uses a directed acyclic graph (DAG) to define dimensional models declaratively. This enables you to define **what** you want in YAML, and the framework builds it automatically.

---

## Documents

| Document | Description |
|----------|-------------|
| [Graph Overview](graph-overview.md) | Introduction to graph-based modeling |
| [Nodes, Edges, Paths](nodes-edges-paths.md) | Core graph components |
| [Cross-Model References](cross-model-references.md) | Inter-model relationships |
| [Dependency Resolution](dependency-resolution.md) | Build order management |
| [Query Planner](query-planner.md) | Dynamic join path discovery |

---

## Core Concepts

### Graph Components

```
┌─────────────────────────────────────────────────┐
│                  Model Graph                     │
├─────────────────────────────────────────────────┤
│                                                 │
│   ┌─────────┐     edge      ┌─────────┐       │
│   │  Node   │──────────────▶│  Node   │       │
│   │ (dim_)  │               │ (fact_) │       │
│   └─────────┘               └────┬────┘       │
│                                  │             │
│                              path│             │
│                                  ▼             │
│                           ┌──────────┐        │
│                           │   View   │        │
│                           │(joined)  │        │
│                           └──────────┘        │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Nodes

Tables (dimensions or facts) defined in YAML:

```yaml
nodes:
  - id: dim_stock
    from: bronze.securities_reference
    select:
      ticker: ticker
      company_name: name
    unique_key: [ticker]

  - id: fact_stock_prices
    from: bronze.securities_prices_daily
    select:
      ticker: ticker
      trade_date: trade_date
      close: close
```

### Edges

Relationships (foreign keys) between nodes:

```yaml
edges:
  - from: fact_stock_prices
    to: dim_stock
    on: [ticker = ticker]

  - from: fact_stock_prices
    to: core.dim_calendar
    on: [trade_date = date]
```

### Paths

Pre-materialized joined views:

```yaml
paths:
  - id: stock_prices_enriched
    hops: fact_stock_prices -> dim_stock -> company.dim_company
```

---

## Model Dependency Graph

```
Tier 0 (Foundation):
  └── core (calendar dimension)

Tier 1 (Independent):
  ├── company (corporate entities)
  └── macro (economic indicators)

Tier 2 (Dependent):
  ├── stocks (depends on: core, company)
  ├── options (depends on: core, stocks)
  └── etfs (depends on: core, stocks)

Tier 3 (Analytics):
  └── forecast (depends on: core, stocks)
```

---

## Build Process

```
1. Load YAML configuration
   ↓
2. Build nodes (load from Bronze, apply transforms)
   ↓
3. Validate edges (test joins)
   ↓
4. Materialize paths (create joined views)
   ↓
5. Separate dims and facts
   ↓
6. Return (dims, facts) dictionaries
```

---

## Cross-Model References

Models can reference tables from other models:

```yaml
# In stocks model
edges:
  - from: dim_stock
    to: company.dim_company  # Cross-model reference
    on: [company_id = company_id]
```

**Resolution**: Framework uses `UniversalSession` to load cross-model tables.

---

## Related Documentation

- [Core Framework](../01-core-framework/) - BaseModel implementation
- [Implemented Models](../04-implemented-models/) - Model examples
- [Configuration](../11-configuration/) - YAML configuration
