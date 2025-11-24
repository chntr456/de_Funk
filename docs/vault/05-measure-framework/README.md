# Measure Framework

**Unified calculation engine for business metrics**

---

## Overview

The Measure Framework provides a declarative, YAML-driven system for defining and executing business metrics across any backend (DuckDB, Spark).

---

## Documents

| Document | Description |
|----------|-------------|
| [Measure Framework](measure-framework.md) | Complete framework reference |
| [YAML Configuration](yaml-configuration.md) | Measure configuration syntax |
| [Model Lifecycle](model-lifecycle.md) | Build and execution lifecycle |
| [Implemented Models](implemented-models.md) | Model inventory |
| [Calendar Dimension](calendar-dimension.md) | Core calendar reference |

---

## Measure Types

### Simple Measures

Direct aggregations (avg, sum, min, max, count):

```yaml
avg_close_price:
  type: simple
  source: fact_stock_prices.close
  aggregation: avg
  description: Average closing price
```

### Computed Measures

Expression-based calculations:

```yaml
daily_dollar_volume:
  type: computed
  source: fact_stock_prices.close
  expression: "close * volume"
  aggregation: sum
```

### Weighted Measures

Weighted aggregations across entities:

```yaml
volume_weighted_price:
  type: weighted
  source: fact_stock_prices.close
  weighting_method: volume
  group_by: [trade_date]
```

### Python Measures (v2.0)

Complex calculations requiring full Python:

```yaml
python_measures:
  sharpe_ratio:
    function: "stocks.measures.calculate_sharpe_ratio"
    params:
      risk_free_rate: 0.045
      window_days: 252
```

---

## Architecture

```
┌─────────────┐
│ YAML Config │ → Defines WHAT to calculate
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Measure   │ → Generates HOW (SQL)
│   Instance  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Backend   │ → Executes WHERE (DuckDB/Spark)
│   Adapter   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ QueryResult │ → Returns unified results
└─────────────┘
```

---

## Usage Example

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("stocks")

# Execute simple measure
result = model.calculate_measure(
    "avg_close_price",
    filters=[{"column": "ticker", "value": "AAPL"}],
    group_by=["trade_date"]
)

# Execute Python measure
sharpe = model.calculate_measure(
    "sharpe_ratio",
    ticker="AAPL",
    window_days=60
)
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Backend Agnostic** | Same measure works on DuckDB and Spark |
| **Auto-Enrichment** | Automatic joins for missing columns |
| **SQL Generation** | Measures generate SQL for transparency |
| **Unified Results** | QueryResult wrapper abstracts differences |
| **Hybrid YAML/Python** | Simple in YAML, complex in Python |

---

## Related Documentation

- [Implemented Models](../04-implemented-models/) - Model measure examples
- [Core Framework](../01-core-framework/) - BaseModel integration
- [Scripts Reference](../08-scripts-reference/) - Measure scripts
