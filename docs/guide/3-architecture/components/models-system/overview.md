# Models System - Overview

## Introduction

The **Models System** provides a flexible, YAML-driven framework for defining domain models (Company, Forecast, etc.) with automatic graph building, cross-model relationships, and unified data access.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              UniversalSession (Entry Point)             │
│  - Multi-model management                               │
│  - Dynamic model loading                                │
│  - Cross-model access                                   │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
    ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ Company │  │Forecast │  │  Macro  │  ...more models
    │  Model  │  │  Model  │  │  Model  │
    └────┬────┘  └────┬────┘  └────┬────┘
         │            │             │
         └────────────┴─────────────┘
                      │
         ┌────────────▼────────────┐
         │       BaseModel         │
         │  - YAML-driven graph    │
         │  - Node loading         │
         │  - Edge application     │
         │  - Path materialization │
         └────────────┬────────────┘
                      │
         ┌────────────┴────────────┐
         │    StorageRouter        │
         │  - Path resolution      │
         │  - Layer mapping        │
         └─────────────────────────┘
```

## Key Components

### 1. BaseModel (`models/base/model.py`)
- Generic graph-building logic
- YAML-driven table definitions
- Automatic node/edge/path creation
- Backend-agnostic (Spark/DuckDB)

### 2. UniversalSession (`models/api/session.py`)
- Multi-model session management
- Dynamic model loading
- Cross-model queries
- Session injection

### 3. ModelRegistry (`models/registry.py`)
- Model discovery from YAML configs
- Model class registration
- Config parsing and validation

### 4. StorageRouter (`models/api/dal.py`)
- Logical to physical path mapping
- Bronze/Silver/Gold layer resolution
- Table name resolution

## Model Definition (YAML)

```yaml
# configs/models/company.yaml
model: company
version: 1

graph:
  nodes:
    # Facts from Bronze
    - id: fact_prices
      from: bronze.polygon.prices_daily
      select:
        date: date
        ticker: ticker
        close: close
        volume: volume

    # Dimensions from Silver
    - id: dim_companies
      from: silver.companies

  edges:
    # Relationships
    - from: fact_prices
      to: dim_companies
      on: ticker = ticker

  paths:
    # Materialized joins
    - id: prices_with_company
      from: fact_prices
      joins:
        - dim_companies

measures:
  price_avg:
    description: "Average closing price"
    source: fact_prices.close
    aggregation: avg
```

## Usage Examples

### Load Models

```python
from models.api.session import UniversalSession

session = UniversalSession(
    connection=conn,
    storage_cfg=storage,
    repo_root=repo_root,
    models=['company', 'forecast']
)

# Access tables
prices = session.get_table('company', 'fact_prices')
forecasts = session.get_table('forecast', 'fact_forecasts')
```

### Cross-Model Access

```python
# Forecast model can access company data via session injection
class ForecastModel(BaseModel):
    def train(self, ticker):
        # Access company model via injected session
        company_model = self.session.get_model_instance('company')
        historical_prices = company_model.get_prices(ticker)
        
        # Train forecast model
        forecast = self._train_arima(historical_prices)
        return forecast
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/models-system/overview.md`
