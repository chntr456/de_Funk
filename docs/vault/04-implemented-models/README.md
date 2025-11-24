# Implemented Models

**Data dictionary for all dimensional models in de_Funk**

---

## Model Inventory

| Model | Status | Tier | Description | Dependencies |
|-------|--------|------|-------------|--------------|
| [core](core/) | Production | 0 | Calendar dimension (foundation) | None |
| [company](company/) | Production | 1 | Corporate entities (CIK-based) | core |
| [stocks](stocks/) | Production | 2 | Stock securities with technicals | core, company |
| [options](options/) | Partial | 2 | Options contracts | core, stocks |
| [etfs](etfs/) | Skeleton | 2 | Exchange-traded funds | core, stocks |
| [futures](futures/) | Skeleton | 2 | Futures contracts | core |
| [macro](macro/) | Production | 1 | Economic indicators (BLS) | core |
| [city_finance](city-finance/) | Production | 2 | Municipal data (Chicago) | core, macro |
| [forecast](forecast/) | Production | 3 | Time series predictions | stocks, macro |

---

## Model Dependency Graph

```
Tier 0 (Foundation)
┌────────────────────────────────────────────────────────────────┐
│                           core                                  │
│                    (calendar dimension)                         │
└───────────────────────────┬────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
Tier 1 (Independent)
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   company    │    │    macro     │    │              │
│  (entities)  │    │ (economic)   │    │              │
└──────┬───────┘    └──────┬───────┘    └──────────────┘
       │                   │
       │    ┌──────────────┤
       │    │              │
       ▼    ▼              ▼
Tier 2 (Dependent)
┌──────────────┐    ┌──────────────┐
│    stocks    │    │ city_finance │
│ (securities) │    │ (municipal)  │
└──────┬───────┘    └──────────────┘
       │
       ├───────────────┬───────────────┐
       ▼               ▼               ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│   options    ││    etfs      ││   futures    │
│  [PARTIAL]   ││  [SKELETON]  ││  [SKELETON]  │
└──────────────┘└──────────────┘└──────────────┘

Tier 3 (Derived)
┌──────────────┐
│   forecast   │
│ (predictions)│
└──────────────┘
```

---

## Model Summary by Status

### Production Models (6)

| Model | Dimensions | Facts | Measures | Data Source |
|-------|------------|-------|----------|-------------|
| **core** | 1 | 0 | 0 | Generated |
| **company** | 1 | 0 (planned: 2) | 4 | Alpha Vantage |
| **stocks** | 1 | 2 | 14+ | Alpha Vantage |
| **macro** | 1 | 4 | 4 | BLS |
| **city_finance** | 2 | 4 | 4 | Chicago |
| **forecast** | 0 | 3 | 3 | Derived |

### Partial/Skeleton Models (3)

| Model | Status | Notes |
|-------|--------|-------|
| **options** | Partial | Schema defined, needs Python implementation |
| **etfs** | Skeleton | Basic structure, needs data integration |
| **futures** | Skeleton | Basic structure, needs data source |

---

## Data Availability Quick Reference

### Securities Data (stocks)

| Table | Records | Date Range | Update Frequency |
|-------|---------|------------|------------------|
| dim_stock | ~1,000+ | Current | Daily |
| fact_stock_prices | ~500K+ | 20+ years | Daily |
| fact_stock_technicals | ~500K+ | Derived | On build |

### Economic Data (macro)

| Table | Records | Date Range | Update Frequency |
|-------|---------|------------|------------------|
| fact_unemployment | ~300+ | 10+ years | Monthly |
| fact_cpi | ~300+ | 10+ years | Monthly |
| fact_employment | ~300+ | 10+ years | Monthly |

### Municipal Data (city_finance)

| Table | Records | Date Range | Update Frequency |
|-------|---------|------------|------------------|
| fact_local_unemployment | ~10K+ | 5+ years | Monthly |
| fact_building_permits | ~100K+ | 5+ years | Daily |

---

## In This Section

### Model Documentation

Each model has detailed documentation:

- **overview.md** - Purpose, dependencies, data source
- **dimensions.md** - Dimension table schemas
- **facts.md** - Fact table schemas
- **measures.md** - Available measures with formulas

### Additional Documentation

- [inheritance/](inheritance/) - YAML inheritance patterns
  - [base-securities.md](inheritance/base-securities.md) - Base template
  - [yaml-inheritance.md](inheritance/yaml-inheritance.md) - How inheritance works

---

## Using Models

### Query via UniversalSession

```python
from core.session.universal_session import UniversalSession

session = UniversalSession(backend="duckdb")

# Access dimension
stocks = session.get_table("stocks", "dim_stock")

# Access fact
prices = session.get_table("stocks", "fact_stock_prices")

# Cross-model join
df = session.query("""
    SELECT s.ticker, s.company_name, p.close
    FROM stocks.dim_stock s
    JOIN stocks.fact_stock_prices p ON s.ticker = p.ticker
    WHERE p.trade_date = '2024-01-15'
""")
```

### Calculate Measures

```python
from models.api.registry import get_model_registry

registry = get_model_registry()
model = registry.get_model("stocks")

# Simple measure
avg_price = model.calculate_measure(
    "avg_close_price",
    filters=[{"column": "ticker", "value": "AAPL"}]
)

# Python measure
sharpe = model.calculate_measure(
    "sharpe_ratio",
    ticker="AAPL",
    window_days=252
)
```

---

## Model Configuration

### YAML Structure (v2.0 Modular)

```
configs/models/{model}/
├── model.yaml      # Metadata, dependencies
├── schema.yaml     # Dimensions, facts, columns
├── graph.yaml      # Nodes, edges, paths
└── measures.yaml   # YAML + Python measures
```

### Inheritance Pattern

```yaml
# stocks/model.yaml
inherits_from: _base.securities

# stocks/schema.yaml
extends: _base.securities.schema
dimensions:
  dim_stock:
    extends: _base.securities._dim_security
```

---

## Related Documentation

- [Graph Architecture](../02-graph-architecture/README.md) - How models are built
- [Measure Framework](../05-measure-framework/README.md) - Measure calculations
- [Data Providers](../03-data-providers/README.md) - Data sources
