# de_Funk Model Quick Reference

## Model Summary Table

| Model | Tier | Purpose | Tables | Dependencies | Status | Data Source |
|-------|------|---------|--------|--------------|--------|-------------|
| **core** | 0 | Calendar dimension | 1 dim | None | ✅ ACTIVE | Seed data |
| **macro** | 1 | BLS economics | 1 dim + 5 facts | core | 🟡 PARTIAL | BLS API |
| **equity/corporate** | 1 | Stock/company data | Various | core | ✅ ACTIVE | Polygon.io |
| **city_finance** | 2 | Chicago municipal | 2 dims + 5 facts | core, macro | 🟡 PARTIAL | Chicago Portal |
| **etf** | 2 | ETF holdings/pricing | 2 dims + 2 facts | core, equity | 🟡 PARTIAL | Multiple sources |
| **forecast** | 3 | Time series predictions | 3 facts | core, equity | 🟡 PARTIAL | Equity data |

---

## Key Features by Model

### CORE Model
- **Primary Table**: `dim_calendar` (2000-2050)
- **Columns**: 25 rich date attributes
- **Usage**: Date filtering, time aggregations, fiscal year calculations
- **Status**: Foundation - always available

### MACRO Model  
- **Data**: National economic indicators
- **Tables**: 
  - `fact_unemployment` (BLS: LNS14000000)
  - `fact_cpi` (BLS: CUUR0000SA0)
  - `fact_employment` (BLS: CES0000000001)
  - `fact_wages` (BLS: CES0500000003)
- **Update**: Monthly
- **Cross-Model**: Feeds into city_finance for local vs national comparison

### CITY_FINANCE Model
- **Data**: Chicago community area economics + permits
- **Tables**:
  - `fact_local_unemployment` (by community area)
  - `fact_building_permits` (with spatial data)
  - `fact_business_licenses`
  - `fact_economic_indicators`
- **Geography**: 77 Chicago community areas
- **Integration**: Compares local unemployment to national (macro model)
- **Unique Feature**: Spatial data (latitude/longitude) for geo-mapping

### ETF Model
- **Data**: ETF holdings, prices, and metadata
- **Key Innovation**: **Weighted measures**
  - Holdings-weighted return calculation
  - Holdings-weighted volume aggregation
- **Cross-Model Integration**: Holdings reference equity stocks
- **Temporal Dimension**: Point-in-time snapshots of portfolio composition

### FORECAST Model
- **Algorithms**: 
  - ARIMA (4 variants: 7d, 14d, 30d, 60d)
  - Prophet (3 variants: 7d, 30d, 60d)
  - Random Forest (2 variants: 14d, 30d)
- **Targets**: Stock prices and trading volume
- **Outputs**: Predictions + confidence intervals + accuracy metrics
- **Data Source**: Equity model historical data

---

## Cross-Model Relationships Map

```
                    core (FOUNDATION)
                      ↓↓↓↓↓
                    (all models)

macro ←────────────→ city_finance
                   (unemployment comparison)

equity ←──────────→ etf ←─────────────→ city_finance
                 (holdings)           (local vs national)

equity ←──────────→ forecast
                 (training data)
```

---

## Data Ingestion Flows

### BLS → MACRO Model
```
BLS API (POST)
  ↓
BLSIngestor (4 series IDs)
  ↓ 
Facets (unemployment_facet, cpi_facet, etc.)
  ↓
Bronze (bls_unemployment, bls_cpi, bls_employment, bls_wages)
  ↓
Silver (fact_unemployment, fact_cpi, fact_employment, fact_wages)
```

### Chicago Portal → CITY_FINANCE Model
```
Socrata API (GET with pagination)
  ↓
ChicagoIngestor (4 datasets)
  ↓
Facets (unemployment_rates_facet, building_permits_facet, etc.)
  ↓
Bronze (chicago_unemployment, chicago_building_permits, chicago_business_licenses)
  ↓
Silver (fact_local_unemployment, fact_building_permits, etc.)
```

### Equity → FORECAST Model
```
Equity Model (fact_equity_prices)
  ↓
Training Pipeline (extract historical data)
  ↓
Model Training (ARIMA, Prophet, RandomForest)
  ↓
Prediction Generation (7/14/30-day horizons)
  ↓
Silver (fact_forecasts, fact_forecast_metrics, fact_model_registry)
```

---

## Configuration Management

All models follow **3-level configuration precedence**:
1. Explicit parameters (code)
2. Environment variables (.env)
3. Configuration files (configs/*.yaml, configs/*.json)

### API Credentials
```bash
# In .env file
BLS_API_KEYS=<api_key>
CHICAGO_API_KEYS=<token>
POLYGON_API_KEYS=<key>
```

### Auto-Discovered Configurations
- `configs/bls_endpoints.json` → Auto-loaded by ConfigLoader
- `configs/chicago_endpoints.json` → Auto-loaded by ConfigLoader
- `configs/polygon_endpoints.json` → Auto-loaded by ConfigLoader

---

## Measures Overview

### CORE Model
- No measures (pure reference data)

### MACRO Model
- `avg_unemployment_rate` - Aggregate unemployment
- `latest_cpi` - Most recent CPI
- `employment_growth` - Total employment
- `wage_trend` - Average wages

### CITY_FINANCE Model
- `avg_local_unemployment` - By community area
- `total_permits_issued` - Count
- `total_permit_fees` - Sum
- `avg_permit_fee` - Average
- `total_labor_force` - Sum

### ETF Model
- `avg_expense_ratio` - Simple aggregate
- `avg_etf_close` - Simple aggregate
- `avg_premium_discount` - NAV comparison
- **`holdings_weighted_return`** - Cross-model weighted! ⭐
- **`holdings_weighted_volume`** - Cross-model weighted! ⭐

### FORECAST Model
- `avg_forecast_error` - MAE aggregate
- `avg_forecast_mape` - MAPE aggregate
- `best_model_r2` - Max R²

---

## Storage Paths

```
storage/silver/
├── core/
│   └── dims/dim_calendar/
├── macro/
│   ├── dims/dim_economic_series/
│   └── facts/fact_unemployment, fact_cpi, fact_employment, fact_wages/
├── city_finance/
│   ├── dims/dim_community_area/, dim_permit_type/
│   └── facts/fact_local_unemployment, fact_building_permits, fact_business_licenses/
├── etf/
│   ├── dims/dim_etf/, dim_etf_holdings/
│   └── facts/fact_etf_prices, etf_prices_with_info/
└── forecast/
    └── facts/forecast_price, forecast_metrics, model_registry/
```

---

## Build & Query Commands

### Build Models
```bash
# Build all models
python scripts/build_all_models.py

# Build specific model
python -m scripts.rebuild_model --model macro

# Ingest data (requires API keys)
python run_full_pipeline.py --top-n 100

# Run forecasts
python scripts/run_forecasts.py
```

### Query Models (Python)
```python
from core.session.universal_session import UniversalSession

# Create session (DuckDB recommended)
session = UniversalSession(backend='duckdb')

# Load model
core = session.load_model('core')
macro = session.load_model('macro')
city = session.load_model('city_finance')

# Query
unemployment = macro.get_unemployment('2024-01-01', '2024-12-31')
local = city.get_local_unemployment()
comparison = city.compare_to_national_unemployment()
```

### Query with Measures
```python
# Calculate measure
result = macro.calculate_measure('avg_unemployment_rate')

# ETF weighted measure (cross-model!)
etf = session.load_model('etf')
weighted_return = etf.calculate_measure('holdings_weighted_return')
```

---

## Special Features

### 1. Temporal Holdings Dimension (ETF Model)
- Holdings tracked by `as_of_date`
- Enables portfolio composition history
- Required for accurate weighted calculations

### 2. Materialized Paths
- `city_finance.unemployment_with_area` - Denormalized query result
- `city_finance.permits_with_area` - Denormalized query result
- `etf.etf_prices_with_info` - Denormalized query result

### 3. Weighted Measures (ETF Model)
- Type: `weighted` (vs simple `avg`/`sum`)
- Joins across models (holdings + prices)
- Custom weighting strategy per measure

### 4. Cross-Model Edges
- All fact tables → core.dim_calendar (date filtering)
- city_finance.unemployment → macro.unemployment (comparison)
- etf.holdings → equity.dim_equity (stock reference)
- forecast.predictions → equity.prices (accuracy tracking)

### 5. Fiscal Calendar Support (CORE Model)
- Configurable fiscal year start month
- Fiscal quarter, month calculations
- Useful for finance-specific analysis

---

## Dependency Resolution Example

**Query: "Get ETF holdings_weighted_return"**

1. Load ETF model (depends on: core, equity, corporate)
2. Load core model (no dependencies) ✓
3. Load equity model (depends on: core) ✓
4. Load corporate model (depends on: core) ✓
5. Get dim_etf_holdings from ETF
6. Get equity.fact_equity_prices from equity
7. Join on (holding_ticker=ticker, as_of_date=trade_date)
8. Weight by holdings percentage
9. Return weighted aggregates

---

## Configuration Files Reference

| File | Purpose | Auto-Discovered | Notes |
|------|---------|---|-------|
| `/configs/models/core.yaml` | Core calendar config | No | YAML-driven |
| `/configs/models/macro.yaml` | Macro model config | No | BLS series IDs |
| `/configs/models/city_finance.yaml` | City finance config | No | Chicago dataset IDs |
| `/configs/models/etf.yaml` | ETF model config | No | Weighted measures |
| `/configs/models/forecast.yaml` | Forecast config | No | 8 model variants |
| `/configs/storage.json` | Storage paths | No | Table mappings |
| `/configs/bls_endpoints.json` | BLS API endpoints | ✅ YES | ConfigLoader |
| `/configs/chicago_endpoints.json` | Chicago API endpoints | ✅ YES | ConfigLoader |
| `/configs/polygon_endpoints.json` | Polygon API endpoints | ✅ YES | ConfigLoader |

---

## Additional Resources

**Comprehensive Analysis**: See `COMPREHENSIVE_MODEL_ANALYSIS.md` for:
- Detailed purpose & scope for each model
- Complete table definitions
- Full data pipeline documentation
- Cross-model relationship details
- Storage structure and maturity status

**Key Documentation Files**:
- `CLAUDE.md` - Overall project architecture
- `TESTING_GUIDE.md` - Test patterns
- `PIPELINE_GUIDE.md` - Data pipeline docs
- `MODEL_DEPENDENCY_ANALYSIS.md` - Dependency issues

