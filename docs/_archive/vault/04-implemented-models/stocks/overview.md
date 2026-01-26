# Stocks Model Overview

**Stock securities with prices and technical indicators**

---

## Summary

| Property | Value |
|----------|-------|
| **Model** | stocks |
| **Version** | 2.0 |
| **Status** | Production |
| **Tier** | 2 |
| **Dependencies** | core, company |
| **Data Source** | Alpha Vantage |
| **Inherits From** | _base.securities |

---

## Purpose

The stocks model provides comprehensive stock market data including:

- **Reference Data**: Ticker info, exchange, sector, CIK
- **Price Data**: Daily OHLCV with adjustments
- **Technical Indicators**: Moving averages, RSI, MACD, Bollinger Bands
- **Measures**: Pre-defined analytics (YAML + Python)

---

## Tables

| Table | Type | Records | Description |
|-------|------|---------|-------------|
| [dim_stock](dimensions.md) | Dimension | ~1,000+ | Stock reference data |
| [fact_stock_prices](facts.md) | Fact | ~500K+ | Daily OHLCV prices |
| [fact_stock_technicals](facts.md) | Fact | ~500K+ | Technical indicators |

---

## Measures

| Category | Count | Examples |
|----------|-------|----------|
| **Simple (YAML)** | 8 | avg_close_price, total_volume |
| **Computed (YAML)** | 3 | price_range, daily_return_avg |
| **Python** | 6 | sharpe_ratio, correlation_matrix |

See [Measures](measures.md) for complete list.

---

## Architecture

### YAML Inheritance

```yaml
# model.yaml
inherits_from: _base.securities

# schema.yaml
extends: _base.securities.schema
dimensions:
  dim_stock:
    extends: _base.securities._dim_security
```

### Model Dependencies

```
core (calendar)
    ↓
company (entities)
    ↓
stocks (securities)
    ↓
options, etfs (derivatives)
```

### Cross-Model Joins

```yaml
edges:
  - from: dim_stock
    to: company.dim_company
    on: [company_id = company_id]

  - from: fact_stock_prices
    to: core.dim_calendar
    on: [trade_date = date]
```

---

## Data Pipeline

```
Alpha Vantage API
    │
    ├── OVERVIEW endpoint → SecuritiesReferenceFacet
    │                            ↓
    │                    securities_reference (Bronze)
    │
    └── TIME_SERIES endpoint → SecuritiesPricesFacet
                                   ↓
                           securities_prices_daily (Bronze)
                                   │
                                   ▼
                         StocksModel.build()
                                   │
            ┌──────────────────────┼──────────────────────┐
            ▼                      ▼                      ▼
      dim_stock           fact_stock_prices      fact_stock_technicals
       (Silver)               (Silver)               (Silver)
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `configs/models/stocks/model.yaml` | Metadata, dependencies |
| `configs/models/stocks/schema.yaml` | Dimension/fact schemas |
| `configs/models/stocks/graph.yaml` | Nodes, edges, paths |
| `configs/models/stocks/measures.yaml` | YAML + Python measures |
| `models/implemented/stocks/measures.py` | Python measure implementations |

---

## Quick Usage

### Access Data

```python
from core.session.universal_session import UniversalSession

session = UniversalSession(backend="duckdb")

# Get dimension
stocks = session.get_table("stocks", "dim_stock")

# Get prices
prices = session.get_table("stocks", "fact_stock_prices")

# Query with join
df = session.query("""
    SELECT d.ticker, d.sector, p.close
    FROM stocks.dim_stock d
    JOIN stocks.fact_stock_prices p ON d.ticker = p.ticker
    WHERE d.ticker = 'AAPL' AND p.trade_date >= '2024-01-01'
""")
```

### Calculate Measures

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("stocks")

# YAML measure
avg_price = model.calculate_measure("avg_close_price", ticker="AAPL")

# Python measure
sharpe = model.calculate_measure("sharpe_ratio", ticker="AAPL", window_days=252)
```

---

## Related Documentation

- [Dimensions](dimensions.md) - dim_stock schema
- [Facts](facts.md) - Price and technical tables
- [Measures](measures.md) - Available calculations
- [Company Model](../company/) - Entity linkage via CIK
