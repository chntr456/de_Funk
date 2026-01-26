# Implemented Models

**Reference for all domain models**

Location: `configs/models/`, `models/implemented/`

---

## Overview

de_Funk implements domain models organized in a tiered dependency hierarchy. All models follow the same YAML-driven graph-based architecture.

**Note**: The framework is domain-agnostic - you can model any domain using the same patterns.

---

## Model Inventory

| Model | Tier | Depends On | Purpose | Tables |
|-------|------|------------|---------|--------|
| core | 0 | - | Time dimension | 1 dim |
| company | 1 | core | Corporate entities | 1 dim |
| macro | 1 | core | Economic indicators | 4 facts |
| stocks | 2 | core, company | Stock securities & prices | 1 dim, 2 facts |
| city_finance | 2 | core, macro | Municipal data | 2 facts |
| forecast | 3 | core, stocks | Price predictions | 3 facts |

---

## Tier 0: Foundation

### core

**Purpose**: Universal calendar dimension

**Location**: `configs/models/core.yaml`

**Tables**:
- `dim_calendar` - Date dimension with year, quarter, month, week attributes (23 columns)

**Usage**: All time-based models reference `core.dim_calendar`

**See**: [Calendar Dimension](calendar-dimension.md)

---

## Tier 1: Core Domains

### company

**Purpose**: Corporate entities (companies linked via CIK)

**Location**: `configs/models/company.yaml`

**Tables**:
- `dim_company` - Company fundamentals, sector, industry, CIK identifier

**Relationships**:
- ← `stocks.dim_stock` (stocks belong to companies via company_id)

**Data Source**: Alpha Vantage API

---

### macro

**Purpose**: Macroeconomic indicators

**Location**: `configs/models/macro.yaml`

**Tables**:
- `dim_economic_series` - Series metadata
- `fact_unemployment` - Unemployment rates by date
- `fact_cpi` - Consumer Price Index
- `fact_employment` - Total nonfarm employment
- `fact_wages` - Average hourly earnings
- `economic_indicators_wide` - Wide-format macro indicators

**Data Source**: Bureau of Labor Statistics (BLS) API

---

## Tier 2: Market Data

### stocks

**Purpose**: Stock securities and daily prices

**Location**: `configs/models/stocks/` (modular: model.yaml, schema.yaml, graph.yaml, measures.yaml)

**Tables**:
- `dim_stock` - Stock instruments (tickers, exchanges, company_id)
- `fact_stock_prices` - Daily OHLCV data
- `fact_stock_technicals` - Technical indicators (SMA, EMA, RSI, MACD)

**Relationships**:
- → `company.dim_company` (stocks belong to companies via company_id)
- → `core.dim_calendar` (prices have dates)

**Data Source**: Alpha Vantage API

**Inheritance**: Extends `_base.securities` template

---

### city_finance

**Purpose**: Municipal finance data

**Location**: `configs/models/city_finance.yaml`

**Tables**:
- `dim_community_area` - Chicago community areas
- `fact_local_unemployment` - Chicago unemployment rates
- `fact_building_permits` - Building permit data

**Relationships**:
- → `core.dim_calendar`
- → `macro` (declared dependency)

**Data Source**: Chicago Data Portal (Socrata API)

---

## Tier 3: Analytics

### forecast

**Purpose**: Time series price predictions

**Location**: `configs/models/forecast.yaml`

**Tables**:
- `fact_forecasts` - Price predictions with confidence intervals
- `fact_forecast_metrics` - Model performance metrics (RMSE, MAE, MAPE)
- `fact_model_registry` - Registry of trained models

**Relationships**:
- → `stocks` (forecasts predict stock prices)
- → `core.dim_calendar`

**Forecast Models**: ARIMA, Prophet, Random Forest

---

## Partial/Skeleton Models

These models have YAML configurations but are not fully implemented:

| Model | Status | Notes |
|-------|--------|-------|
| options | Partial | Schema defined, needs Python implementation |
| etfs | Skeleton | Basic structure, needs data integration |
| futures | Skeleton | Basic structure, needs data source |

---

## Model Statistics

| Stat | Count |
|------|-------|
| **Production models** | 6 |
| **Total dimensions** | 5 |
| **Total facts** | 12+ |
| **Cross-model edges** | 6 |
| **Measures defined** | 30+ |

---

## Adding New Models

To add a new model:

1. **Create YAML**: `configs/models/new_model/` (modular) or `configs/models/new_model.yaml`
2. **Define schema**: dimensions, facts, columns
3. **Define graph**: nodes, edges, paths
4. **Define measures**: simple, computed, weighted, Python
5. **Create Bronze data**: Run ingestion pipeline
6. **Build model**: `python -m scripts.build.rebuild_model --model new_model`

---

## Model File Locations

**YAML Configs**:
- Modular (v2.0): `/configs/models/{model}/model.yaml`, `schema.yaml`, `graph.yaml`, `measures.yaml`
- Single file (v1.x): `/configs/models/{model}.yaml`

**Python Implementations**: `/models/implemented/{model}/`
- Most models don't need custom Python (YAML is enough)
- Custom Python for special logic or Python measures

**Example Custom Model**:
```python
# models/implemented/stocks/model.py
class StocksModel(BaseModel):
    """Stocks model with technical indicators."""

    def after_build(self):
        # Calculate technical indicators
        self._calculate_technicals()
```

---

## Related Documentation

- [Model Lifecycle](model-lifecycle.md) - Build process
- [YAML Configuration](yaml-configuration.md) - Config format
- [Dependency Resolution](../02-graph-architecture/dependency-resolution.md) - Build order
- [BaseModel](../01-core-framework/base-model.md) - Implementation
