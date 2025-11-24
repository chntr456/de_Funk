# Implemented Models

**Reference for all 8 domain models**

Location: `configs/models/`, `models/implemented/`

---

## Overview

de_Funk currently implements **8 domain models** organized in a 3-tier dependency hierarchy. All models follow the same YAML-driven graph-based architecture.

**Note**: The framework is domain-agnostic - you can model any domain using the same patterns.

---

## Model Inventory

| Model | Tier | Depends On | Purpose | Tables |
|-------|------|------------|---------|--------|
| core | 0 | - | Time dimension | 1 dim |
| macro | 1 | core | Economic indicators | 3 facts |
| corporate | 1 | core | Company entities | 1 dim |
| equity | 2 | core, corporate | Securities & prices | 1 dim, 1 fact |
| city_finance | 2 | core, macro | Municipal data | 2 facts |
| etf | 3 | core, equity | ETF holdings | 1 dim, 1 fact |
| forecast | 3 | core, equity | Price predictions | 2 facts |
| ~~company~~ | - | core | **DEPRECATED** | - |

---

## Tier 0: Foundation

### core

**Purpose**: Universal calendar dimension

**Location**: `configs/models/core.yaml`

**Tables**:
- `dim_calendar` - Date dimension with year, quarter, month, week attributes

**Usage**: All time-based models reference `core.dim_calendar`

**See**: [Calendar Dimension](calendar-dimension.md)

---

## Tier 1: Core Domains

### macro

**Purpose**: Macroeconomic indicators

**Location**: `configs/models/macro.yaml`

**Tables**:
- `fact_unemployment` - Unemployment rates by date
- `fact_cpi` - Consumer Price Index
- `economic_indicators_wide` - Wide-format macro indicators

**Data Source**: Bureau of Labor Statistics (BLS) API

---

### corporate

**Purpose**: Corporate entities (companies)

**Location**: `configs/models/corporate.yaml`

**Tables**:
- `dim_corporate` - Company fundamentals, sector, industry

**Relationships**:
- ↔ `equity.dim_equity` (bidirectional - companies have tickers, tickers belong to companies)

---

## Tier 2: Market Data

### equity

**Purpose**: Tradable securities and stock prices

**Location**: `configs/models/equity.yaml`

**Tables**:
- `dim_equity` - Equity instruments (tickers, exchanges)
- `fact_equity_prices` - Daily OHLCV data

**Relationships**:
- → `corporate.dim_corporate` (equities belong to companies)
- → `core.dim_calendar` (prices have dates)

**Data Source**: Polygon.io API

---

### city_finance

**Purpose**: Municipal finance data

**Location**: `configs/models/city_finance.yaml`

**Tables**:
- `fact_local_unemployment` - Chicago unemployment rates
- `fact_building_permits` - Building permit data

**Relationships**:
- → `core.dim_calendar`
- → `macro` (declared dependency, edge not yet implemented)

**Data Source**: Chicago Data Portal (Socrata API)

---

## Tier 3: Portfolio & Analytics

### etf

**Purpose**: ETF holdings and prices

**Location**: `configs/models/etf.yaml`

**Tables**:
- `dim_etf_holdings` - Fund composition
- `fact_etf_prices` - ETF price history

**Relationships**:
- → `equity.dim_equity` (holdings reference equities)
- → `core.dim_calendar`

**Data Source**: Polygon.io API

**Status**: ⚠️ Currently references deprecated `company` model - needs migration to `equity`

---

### forecast

**Purpose**: Time series price predictions

**Location**: `configs/models/forecast.yaml`

**Tables**:
- `fact_forecasts` - Price predictions with confidence intervals
- `fact_forecast_metrics` - Model performance metrics (RMSE, MAE, etc.)

**Relationships**:
- → `equity` (forecasts predict equity prices)
- → `core.dim_calendar`

**Forecast Models**: ARIMA, Prophet, Linear Regression

**Status**: ⚠️ Currently references deprecated `company` model - needs migration

---

## Deprecated Models

### ~~company~~ (DEPRECATED)

**Status**: Being migrated to `equity` + `corporate` split

**Issue**: Still referenced by `etf` and `forecast` models

**Action Required**: Update all references to use `equity`/`corporate`

**See**: [Dependency Resolution](../02-graph-architecture/dependency-resolution.md#critical-issues)

---

## Model Statistics

| Stat | Count |
|------|-------|
| **Active models** | 7 |
| **Total dimensions** | 4 |
| **Total facts** | 9 |
| **Cross-model edges** | 8 |
| **Measures defined** | 20+ |

---

## Adding New Models

To add a new model:

1. **Create YAML**: `configs/models/new_model.yaml`
2. **Define schema**: dimensions, facts, columns
3. **Define graph**: nodes, edges, paths
4. **Define measures**: simple, computed, weighted
5. **Create Bronze data**: Run ingestion pipeline
6. **Build model**: `python scripts/rebuild_model.py --model new_model`

**Example Domains** (not yet implemented):
- Options (derivatives)
- Crypto (cryptocurrency)
- FX (foreign exchange)
- Commodities
- Fixed Income

---

## Model File Locations

**YAML Configs**: `/configs/models/{model}.yaml`

**Python Implementations**: `/models/implemented/{model}/`
- Most models don't need custom Python (YAML is enough)
- Custom Python only for special logic

**Example Custom Model**:
```python
# models/implemented/equity/equity_model.py
class EquityModel(BaseModel):
    """Equity model with custom ticker validation."""

    def before_build(self):
        # Custom validation before build
        self.validate_tickers()
```

---

## Related Documentation

- [Model Lifecycle](model-lifecycle.md) - Build process
- [YAML Configuration](yaml-configuration.md) - Config format
- [Dependency Resolution](../02-graph-architecture/dependency-resolution.md) - Build order
- [BaseModel](../01-core-components/base-model.md) - Implementation
