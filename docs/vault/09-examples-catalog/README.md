# Examples Catalog

**Runnable code examples for de_Funk**

---

## Overview

The examples catalog provides runnable code examples demonstrating de_Funk's capabilities. All examples are located in `scripts/examples/`.

---

## Quick Start

```bash
# Start here - complete quickstart
python -m scripts.examples.00_QUICKSTART
```

---

## Example Categories

| Category | Location | Description |
|----------|----------|-------------|
| [Quickstart](#quickstart) | `scripts/examples/` | Getting started |
| [Measure Calculations](#measure-calculations) | `scripts/examples/measure_calculations/` | Using measures |
| [Weighting Strategies](#weighting-strategies) | `scripts/examples/weighting_strategies/` | Portfolio weighting |
| [Queries](#queries) | `scripts/examples/queries/` | Query patterns |
| [Extending](#extending) | `scripts/examples/extending/` | Custom extensions |
| [Backend Comparison](#backend-comparison) | `scripts/examples/backend_comparison/` | DuckDB vs Spark |

---

## Quickstart

**File**: `scripts/examples/00_QUICKSTART.py`

```bash
python -m scripts.examples.00_QUICKSTART
```

Demonstrates:
- Loading models
- Basic queries
- Simple measure execution
- Filter application

---

## Measure Calculations

**Location**: `scripts/examples/measure_calculations/`

### 01_basic_measures.py

```bash
python -m scripts.examples.measure_calculations.01_basic_measures
```

Demonstrates:
- Simple measure execution
- Filtering by ticker
- Grouping by date

### 02_troubleshooting.py

```bash
python -m scripts.examples.measure_calculations.02_troubleshooting
```

Demonstrates:
- Debug techniques
- Common error resolution
- Measure validation

---

## Weighting Strategies

**Location**: `scripts/examples/weighting_strategies/`

### 01_basic_weighted_price.py

```bash
python -m scripts.examples.weighting_strategies.01_basic_weighted_price
```

Demonstrates:
- Volume-weighted average price
- Market-cap weighting
- Equal weighting

### Weighting Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| `equal` | Equal weight per entity | Simple average |
| `volume` | Weight by trading volume | Price indices |
| `market_cap` | Weight by market cap | S&P 500 style |
| `custom` | Custom weight column | User-defined |

---

## Queries

**Location**: `scripts/examples/queries/`

### 01_auto_join.py

```bash
python -m scripts.examples.queries.01_auto_join
```

Demonstrates:
- Automatic table joins
- Cross-model queries
- Query planner usage

### Query Patterns

```python
# Direct table query
df = session.query("""
    SELECT ticker, close_price
    FROM stocks.fact_stock_prices
    WHERE trade_date >= '2024-01-01'
""")

# Cross-model join
df = session.query("""
    SELECT
        s.ticker,
        s.close_price,
        c.company_name,
        c.sector
    FROM stocks.dim_stock s
    JOIN company.dim_company c
        ON s.company_id = c.company_id
""")
```

---

## Extending

**Location**: `scripts/examples/extending/`

Demonstrates:
- Creating custom models
- Adding new measures
- Custom facet implementation
- Provider development

### Custom Model Example

```python
from models.base.model import BaseModel

class CustomModel(BaseModel):
    def before_build(self):
        print("Starting build...")

    def custom_node_loading(self, node_id, node_config):
        if node_id == "dim_custom":
            return self._load_custom_dimension()
        return None
```

---

## Backend Comparison

**Location**: `scripts/examples/backend_comparison/`

Demonstrates:
- DuckDB vs Spark performance
- Backend-specific features
- Choosing the right backend

### Performance Comparison

| Operation | DuckDB | Spark |
|-----------|--------|-------|
| Simple query | 10-100x faster | Baseline |
| Large joins | 10-50x faster | Baseline |
| Window functions | 10-50x faster | Baseline |
| Distributed | N/A | Supported |

---

## Parameter Interface

**Location**: `scripts/examples/parameter_interface/`

Demonstrates:
- Calculator interface
- Parameter passing
- Runtime configuration

---

## Running Examples

```bash
# Run specific example
python -m scripts.examples.{category}.{example_name}

# Examples
python -m scripts.examples.00_QUICKSTART
python -m scripts.examples.measure_calculations.01_basic_measures
python -m scripts.examples.weighting_strategies.01_basic_weighted_price
python -m scripts.examples.queries.01_auto_join
```

---

## Related Documentation

- [Scripts Reference](../08-scripts-reference/) - All script documentation
- [Measure Framework](../05-measure-framework/) - Measure details
- [Core Framework](../01-core-framework/) - Component documentation
