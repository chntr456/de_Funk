# Core Framework

**Foundation components for de_Funk**

---

## Overview

The core framework provides the foundational components that power de_Funk's model building, querying, and data access capabilities.

---

## Components

| Document | Description |
|----------|-------------|
| [BaseModel](base-model.md) | Foundation class for all dimensional models |
| [Universal Session](universal-session.md) | Unified query interface across models |
| [Connection System](connection-system.md) | Database connection management |
| [Filter Engine](filter-engine.md) | Backend-agnostic filter application |
| [Storage Router](storage-router.md) | Bronze/Silver path resolution |
| [Logging & Error Handling](logging-error-handling.md) | Centralized logging and exception framework |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                   Universal Session                   │
│   (Cross-model queries, measure execution, filters)  │
└──────────────────┬───────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ▼                       ▼
┌──────────────┐       ┌──────────────┐
│  BaseModel   │       │ Filter Engine │
│  (per model) │       │  (backend    │
│              │       │   agnostic)  │
└──────┬───────┘       └──────────────┘
       │
       ▼
┌──────────────┐       ┌──────────────┐
│  Connection  │◄──────│   Storage    │
│   System     │       │   Router     │
└──────────────┘       └──────────────┘
```

---

## Key Concepts

### BaseModel

The `BaseModel` class is the foundation for all dimensional models. It provides:

- **YAML-driven graph building**: Nodes, edges, paths from configuration
- **Lazy loading**: Tables built on first access
- **Backend abstraction**: Same code works with Spark or DuckDB
- **Cross-model references**: Access tables from other models

### Universal Session

The `UniversalSession` provides a unified interface for:

- Querying across multiple models
- Executing measures
- Applying filters
- Managing model dependencies

### Connection System

Manages database connections for:

- **DuckDB**: Analytics backend
- **Spark**: Distributed processing backend

### Filter Engine

Backend-agnostic filter application:

- Translate filter specifications to SQL
- Push filters to storage layer
- Support complex conditions (ranges, IN clauses, etc.)

### Storage Router

Resolves storage paths for:

- **Bronze**: Raw ingested data (`storage/bronze/{provider}/{table}/`)
- **Silver**: Dimensional models (`storage/silver/{model}/{table}/`)

---

## Usage Example

```python
from core.context import RepoContext
from models.api.registry import get_model_registry

# Initialize context
ctx = RepoContext.from_repo_root(connection_type="duckdb")
registry = get_model_registry()

# Get model instance
model = registry.create_model_instance(
    "stocks",
    connection=ctx.connection,
    storage=ctx.storage
)

# Access tables (lazy builds on first access)
dim_stock = model.get_table("dim_stock")
fact_prices = model.get_table("fact_stock_prices")

# Calculate measures
result = model.calculate_measure(
    "avg_close_price",
    filters=[{"column": "ticker", "value": "AAPL"}]
)
```

---

## Related Documentation

- [Graph Architecture](../02-graph-architecture/) - Graph-based modeling
- [Measure Framework](../05-measure-framework/) - Calculation engine
- [Configuration](../11-configuration/) - Configuration system
